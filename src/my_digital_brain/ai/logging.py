from __future__ import annotations

import logging
from typing import Any

from my_digital_brain.logging import LOG_RECORD_ATTRS


def log_event(
    logger: logging.Logger,
    event: str,
    level: str = "info",
    **fields: Any,
) -> None:
    """Small structured logging helper used by AI client internals."""

    method = getattr(logger, level.lower(), logger.info)
    compact_fields = {key: value for key, value in fields.items() if value is not None}
    extra = {"event": event}
    for key, value in compact_fields.items():
        extra[_safe_extra_key(key)] = value
    method(event, extra=extra)


def _safe_extra_key(key: str) -> str:
    normalized = str(key)
    if normalized in LOG_RECORD_ATTRS or normalized in {"event", "message", "asctime"}:
        return f"event_{normalized}"
    return normalized
