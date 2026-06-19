from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler

from my_digital_brain.ai.logging import log_event
from my_digital_brain.logging import (
    JsonLogFormatter,
    configure_logging,
    sanitize_log_value,
)


def test_json_formatter_redacts_and_omits_noisy_fields() -> None:
    record = logging.LogRecord(
        name="my_digital_brain.graph.service",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="graph.write.failed",
        args=(),
        exc_info=None,
    )
    record.event = "graph.write.failed"
    record.api_key = "secret-key"
    record.contact = "email me@example.com or +39 333 123 4567 @marco"
    record.raw_prompt = "full user memory prompt"

    payload = json.loads(JsonLogFormatter().format(record))

    assert payload["event"] == "graph.write.failed"
    assert payload["api_key"] == "[redacted]"
    assert "[redacted-email]" in payload["contact"]
    assert "[redacted-phone]" in payload["contact"]
    assert "@[redacted-user]" in payload["contact"]
    assert "raw_prompt" not in payload


def test_sanitizer_truncates_large_values_and_redacts_secret_keys() -> None:
    payload = sanitize_log_value(
        {
            "token": "secret-token",
            "summary": "x" * 1200,
            "values": list(range(25)),
        }
    )

    assert payload["token"] == "[redacted]"
    assert len(payload["summary"]) == 1000
    assert payload["summary"].endswith("...")
    assert payload["values"][-1] == {"truncated_items": 5}


def test_configure_logging_routes_application_and_agentic_streams(tmp_path) -> None:
    configure_logging(
        "INFO",
        log_dir=tmp_path,
        app_level="INFO",
        agentic_level="DEBUG",
        max_bytes=2048,
        backup_count=2,
    )

    app_logger = logging.getLogger("my_digital_brain.graph.service")
    ai_logger = logging.getLogger("my_digital_brain.ai.client.core")

    app_logger.info(
        "graph.health.ok",
        extra={"event": "graph.health.ok", "component": "graph", "status": "ok"},
    )
    log_event(
        ai_logger,
        "llm.call.error",
        "error",
        component="genai",
        status="error",
        model="smart-model",
        error_code="missing_role",
        message_count=2,
        message_role_counts={"system": 1, "unknown": 1},
        raw_messages=[{"source": "no role"}],
    )
    _flush_handlers()

    app_lines = (tmp_path / "application.jsonl").read_text(encoding="utf-8").splitlines()
    agentic_lines = (tmp_path / "agentic.jsonl").read_text(encoding="utf-8").splitlines()
    app_payloads = [json.loads(line) for line in app_lines]
    agentic_payloads = [json.loads(line) for line in agentic_lines]

    assert [payload["event"] for payload in app_payloads] == ["graph.health.ok"]
    assert all(payload["logger"].startswith("my_digital_brain.graph") for payload in app_payloads)
    assert [payload["event"] for payload in agentic_payloads] == ["llm.call.error"]
    assert agentic_payloads[0]["message_count"] == 2
    assert agentic_payloads[0]["message_role_counts"] == {"system": 1, "unknown": 1}
    assert "raw_messages" not in agentic_payloads[0]


def test_console_handler_emits_errors_only(tmp_path, capsys) -> None:
    configure_logging("INFO", log_dir=tmp_path)
    logger = logging.getLogger("my_digital_brain.graph.service")

    logger.info("graph.info", extra={"event": "graph.info"})
    logger.error("graph.error", extra={"event": "graph.error"})
    _flush_handlers()

    captured = capsys.readouterr()
    assert "graph.error" in captured.err
    assert "graph.info" not in captured.err


def test_configure_logging_is_idempotent_and_uses_rotation_settings(tmp_path) -> None:
    configure_logging("INFO", log_dir=tmp_path, max_bytes=1234, backup_count=3)
    configure_logging("INFO", log_dir=tmp_path, max_bytes=1234, backup_count=3)

    root_file_handlers = [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, RotatingFileHandler)
    ]
    agentic_file_handlers = [
        handler
        for handler in logging.getLogger("my_digital_brain.ai").handlers
        if isinstance(handler, RotatingFileHandler)
    ]

    assert len(root_file_handlers) == 1
    assert len(agentic_file_handlers) == 1
    assert root_file_handlers[0].maxBytes == 1234
    assert root_file_handlers[0].backupCount == 3
    assert agentic_file_handlers[0].maxBytes == 1234
    assert agentic_file_handlers[0].backupCount == 3


def test_configure_logging_can_truncate_existing_log_files(tmp_path) -> None:
    app_log = tmp_path / "application.jsonl"
    agentic_log = tmp_path / "agentic.jsonl"
    app_log.write_text("old app\n", encoding="utf-8")
    agentic_log.write_text("old agentic\n", encoding="utf-8")

    configure_logging("INFO", log_dir=tmp_path, truncate_on_start=True)
    logging.getLogger("my_digital_brain.graph.service").info(
        "graph.health.ok",
        extra={"event": "graph.health.ok"},
    )
    _flush_handlers()

    assert "old app" not in app_log.read_text(encoding="utf-8")
    assert "old agentic" not in agentic_log.read_text(encoding="utf-8")


def test_configure_logging_suppresses_chroma_telemetry_noise(tmp_path) -> None:
    configure_logging("INFO", log_dir=tmp_path)
    logging.getLogger("chromadb.telemetry.product.posthog").error(
        "Failed to send telemetry event ClientStartEvent",
        extra={"event": "Failed"},
    )
    _flush_handlers()

    assert (tmp_path / "application.jsonl").read_text(encoding="utf-8") == ""


def _flush_handlers() -> None:
    seen: set[int] = set()
    for logger in [
        logging.getLogger(),
        logging.getLogger("my_digital_brain.ai"),
        logging.getLogger("my_digital_brain.agentic"),
        logging.getLogger("my_digital_brain.ingestion"),
    ]:
        for handler in logger.handlers:
            identifier = id(handler)
            if identifier in seen:
                continue
            seen.add(identifier)
            handler.flush()
