from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import sys
from typing import Any


DEFAULT_LOG_DIR = Path("data/logs")
DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_LOG_BACKUP_COUNT = 5
MAX_LOG_STRING_CHARS = 1_000
MAX_LOG_COLLECTION_ITEMS = 20

AGENTIC_LOGGER_PREFIXES = (
    "my_digital_brain.agentic",
    "my_digital_brain.ai",
    "my_digital_brain.ingestion",
)

STANDARD_JSON_FIELDS = (
    "event",
    "component",
    "status",
    "error_code",
    "error_type",
    "state_id",
    "model_task",
    "model",
    "provider",
    "tool_name",
    "handoff_target",
    "conversation_id",
    "session_id",
    "pending_process_id",
    "ingestion_id",
    "duration_ms",
    "latency_ms",
    "message_count",
    "message_role_counts",
    "route",
    "schema_id",
    "source_id",
    "prompt_fingerprint",
    "tool_count",
    "tool_names",
    "toolbox_name",
)

NOISY_KEYS = {
    "args",
    "exc_info",
    "exc_text",
    "stack_info",
    "raw_response",
    "raw_request",
    "raw_messages",
    "messages",
    "prompt",
    "system_prompt",
    "input_message",
    "raw_prompt",
    "raw_graph",
    "graph_payload",
    "embeddings",
    "embedding",
}

SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|token|password|secret|credential|authorization|bearer)",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d(). \-]{6,}\d)")
HANDLE_RE = re.compile(r"(?<!\S)@[A-Za-z0-9_]{2,32}")

LOG_RECORD_ATTRS = set(logging.makeLogRecord({}).__dict__)
LOG_RECORD_ATTRS.update({"message", "asctime"})


class JsonLogFormatter(logging.Formatter):
    """Small JSONL formatter for LLM-readable local logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": _event_name(record),
            "message": sanitize_log_value(record.getMessage(), key="message"),
        }
        for field in STANDARD_JSON_FIELDS:
            if field == "event" and payload.get("event"):
                continue
            if hasattr(record, field):
                payload[field] = sanitize_log_value(getattr(record, field), key=field)

        extra = _record_extra(record)
        if extra:
            for key, value in extra.items():
                if key in payload:
                    continue
                sanitized = sanitize_log_value(value, key=key)
                if sanitized is not None:
                    payload[key] = sanitized

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(
            {key: value for key, value in payload.items() if value is not None},
            ensure_ascii=True,
            sort_keys=True,
            default=str,
        )


class NamespaceExclusionFilter(logging.Filter):
    def __init__(self, excluded_prefixes: tuple[str, ...]) -> None:
        super().__init__()
        self.excluded_prefixes = excluded_prefixes

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith(self.excluded_prefixes)


def configure_logging(
    level: str = "INFO",
    *,
    log_dir: str | Path = DEFAULT_LOG_DIR,
    app_level: str | None = None,
    agentic_level: str | None = None,
    max_bytes: int = DEFAULT_LOG_MAX_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> None:
    """Configure deterministic application and agentic JSONL log streams."""

    base_level = _log_level(level)
    app_resolved_level = _log_level(app_level or level)
    agentic_resolved_level = _log_level(agentic_level or level)
    resolved_log_dir = Path(log_dir)
    resolved_log_dir.mkdir(parents=True, exist_ok=True)

    formatter = JsonLogFormatter()
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.ERROR)
    console.setFormatter(formatter)

    app_file = RotatingFileHandler(
        resolved_log_dir / "application.jsonl",
        maxBytes=max(1, int(max_bytes)),
        backupCount=max(0, int(backup_count)),
        encoding="utf-8",
    )
    app_file.setLevel(app_resolved_level)
    app_file.setFormatter(formatter)
    app_file.addFilter(NamespaceExclusionFilter(AGENTIC_LOGGER_PREFIXES))

    agentic_file = RotatingFileHandler(
        resolved_log_dir / "agentic.jsonl",
        maxBytes=max(1, int(max_bytes)),
        backupCount=max(0, int(backup_count)),
        encoding="utf-8",
    )
    agentic_file.setLevel(agentic_resolved_level)
    agentic_file.setFormatter(formatter)

    root = logging.getLogger()
    _reset_handlers(root)
    root.setLevel(min(base_level, app_resolved_level, agentic_resolved_level, logging.ERROR))
    root.addHandler(app_file)
    root.addHandler(console)

    for logger_name in AGENTIC_LOGGER_PREFIXES:
        logger = logging.getLogger(logger_name)
        _reset_handlers(logger)
        logger.setLevel(agentic_resolved_level)
        logger.propagate = False
        logger.addHandler(agentic_file)
        logger.addHandler(console)


def sanitize_log_value(value: Any, *, key: str | None = None) -> Any:
    if key and _is_noisy_key(key):
        return None
    if key and SECRET_KEY_RE.search(str(key)):
        return "[redacted]"
    if isinstance(value, str):
        return _truncate(_redact_text(value), MAX_LOG_STRING_CHARS)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return _sanitize_mapping(value)
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        sanitized = [
            sanitize_log_value(item)
            for item in items[:MAX_LOG_COLLECTION_ITEMS]
        ]
        if len(items) > MAX_LOG_COLLECTION_ITEMS:
            sanitized.append({"truncated_items": len(items) - MAX_LOG_COLLECTION_ITEMS})
        return sanitized
    if hasattr(value, "model_dump"):
        try:
            return sanitize_log_value(value.model_dump(mode="json", exclude_none=True))
        except Exception:
            return _truncate(_redact_text(str(value)), MAX_LOG_STRING_CHARS)
    return _truncate(_redact_text(str(value)), MAX_LOG_STRING_CHARS)


def _sanitize_mapping(value: dict[Any, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for index, (raw_key, item) in enumerate(value.items()):
        if index >= MAX_LOG_COLLECTION_ITEMS:
            sanitized["truncated_items"] = len(value) - MAX_LOG_COLLECTION_ITEMS
            break
        key = str(raw_key)
        clean = sanitize_log_value(item, key=key)
        if clean is not None:
            sanitized[key] = clean
    return sanitized


def _event_name(record: logging.LogRecord) -> str:
    event = getattr(record, "event", None)
    if event:
        return str(event)
    message = str(record.msg or "")
    return message.split(" ", 1)[0] if message else record.name


def _record_extra(record: logging.LogRecord) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in LOG_RECORD_ATTRS and not key.startswith("_")
    }


def _is_noisy_key(key: str) -> bool:
    normalized = key.strip().lower()
    return normalized in NOISY_KEYS or normalized.startswith("raw_")


def _redact_text(value: str) -> str:
    redacted = EMAIL_RE.sub("[redacted-email]", value)
    redacted = PHONE_RE.sub("[redacted-phone]", redacted)
    redacted = HANDLE_RE.sub("@[redacted-user]", redacted)
    return redacted


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 3)] + "..."


def _reset_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass


def _log_level(value: str | int | None) -> int:
    if isinstance(value, int):
        return value
    return getattr(logging, str(value or "INFO").strip().upper(), logging.INFO)
