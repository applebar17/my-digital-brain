from __future__ import annotations

import logging
from typing import Any


def log_event(
    logger: logging.Logger,
    event: str,
    level: str = "info",
    **fields: Any,
) -> None:
    """Small structured logging helper used by AI client internals."""

    method = getattr(logger, level.lower(), logger.info)
    compact_fields = {key: value for key, value in fields.items() if value is not None}
    if compact_fields:
        rendered = " ".join(f"{key}={value}" for key, value in compact_fields.items())
        method("%s %s", event, rendered)
        return
    method("%s", event)
