from __future__ import annotations


class IngestionError(Exception):
    """Base error for ingestion orchestration failures."""


class IngestionValidationError(IngestionError):
    """Raised when an ingestion contract cannot be converted into a safe graph action."""
