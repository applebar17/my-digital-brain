"""Small logging boundary for the reference client package."""

from __future__ import annotations

import logging


def log_message(logger: logging.Logger | None, message: str, level: str = "info") -> None:
    """Log through a configured logger without an external utility dependency."""

    if logger is None:
        return
    method = getattr(logger, level.lower(), logger.info)
    method(message)
