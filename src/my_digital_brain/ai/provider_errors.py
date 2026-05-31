"""Normalized provider error taxonomy."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .client.errors import _provider_error_details


class ProviderErrorCode(StrEnum):
    AUTH_ERROR = "auth_error"
    RATE_LIMITED = "rate_limited"
    CONTEXT_TOO_LARGE = "context_too_large"
    INVALID_REQUEST = "invalid_request"
    INVALID_SCHEMA = "invalid_schema"
    CONTENT_FILTER = "content_filter"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    UNKNOWN_PROVIDER_ERROR = "unknown_provider_error"


class ProviderError(BaseModel):
    code: ProviderErrorCode
    message: str
    provider_error_code: str | int | None = None
    provider_status: str | int | None = None
    type: str | None = None
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


def normalize_provider_exception(exc: Exception) -> ProviderError:
    details = _provider_error_details(exc)
    provider_status = details.get("provider_status") or getattr(exc, "status_code", None)
    provider_error_code = details.get("provider_error_code") or details.get("error_code")
    text = _error_text(exc, details)
    code = _classify_provider_error(
        provider_status=provider_status,
        provider_error_code=provider_error_code,
        text=text,
    )
    return ProviderError(
        code=code,
        message=str(exc) or code.value,
        provider_error_code=provider_error_code,
        provider_status=provider_status,
        type=details.get("provider_error_type") or exc.__class__.__name__,
        retryable=_is_retryable(code, provider_status),
        details={key: value for key, value in details.items() if value is not None},
    )


def _classify_provider_error(
    *,
    provider_status: Any,
    provider_error_code: Any,
    text: str,
) -> ProviderErrorCode:
    status = _safe_int(provider_status)
    raw_code = str(provider_error_code or "").strip().lower().replace("-", "_")
    if raw_code == "content_filter" or "content_filter" in text:
        return ProviderErrorCode.CONTENT_FILTER
    if status in {401, 403} or "authentication" in text or "api key" in text:
        return ProviderErrorCode.AUTH_ERROR
    if status == 429 or "rate limit" in text or "too many requests" in text:
        return ProviderErrorCode.RATE_LIMITED
    if "context" in text and ("length" in text or "token" in text or "maximum" in text):
        return ProviderErrorCode.CONTEXT_TOO_LARGE
    if "schema" in text or "response_format" in text or "json schema" in text:
        return ProviderErrorCode.INVALID_SCHEMA
    if status in {408, 500, 502, 503, 504}:
        return ProviderErrorCode.PROVIDER_UNAVAILABLE
    if status == 400 or "invalid_request" in raw_code or "invalid request" in text:
        return ProviderErrorCode.INVALID_REQUEST
    return ProviderErrorCode.UNKNOWN_PROVIDER_ERROR


def _is_retryable(code: ProviderErrorCode, provider_status: Any) -> bool:
    if code in {
        ProviderErrorCode.RATE_LIMITED,
        ProviderErrorCode.PROVIDER_UNAVAILABLE,
    }:
        return True
    status = _safe_int(provider_status)
    return status in {408, 429, 500, 502, 503, 504}


def _error_text(exc: Exception, details: dict[str, Any]) -> str:
    values = [
        str(exc),
        getattr(exc, "code", None),
        getattr(exc, "status_code", None),
        getattr(exc, "body", None),
        details.get("error_code"),
        details.get("provider_error_code"),
        details.get("provider_error_type"),
        details.get("content_filter_summary"),
    ]
    return " ".join(str(value).lower() for value in values if value is not None)


def _safe_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
