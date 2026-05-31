"""Provider request-log payload shaping."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .provider_errors import ProviderError
from .schemas import (
    AIRequestContext,
    ModelRoute,
    ProviderCallMetadata,
    ProviderUsage,
)


class ProviderRequestLogPayload(BaseModel):
    provider: str
    operation: str | None = None
    model: str | None = None
    deployment: str | None = None
    request_id: str | None = None
    status: Literal["ok", "error"] = "ok"
    source_id: str | None = None
    conversation_id: str | None = None
    prompt_id: str | None = None
    prompt_version: str | None = None
    schema_id: str | None = None
    schema_version: str | None = None
    privacy_level: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    audio_seconds: float | None = None
    estimated_cost: float | None = None
    currency: str | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_provider_request_log_payload(
    *,
    context: AIRequestContext | None = None,
    route: ModelRoute | None = None,
    call_metadata: ProviderCallMetadata | None = None,
    usage: ProviderUsage | None = None,
    error: ProviderError | None = None,
    operation: str | None = None,
) -> ProviderRequestLogPayload:
    resolved_context = context or AIRequestContext()
    provider = (
        call_metadata.provider
        if call_metadata is not None
        else route.provider if route is not None else "unknown"
    )
    model = (
        call_metadata.model
        if call_metadata is not None and call_metadata.model is not None
        else route.model if route is not None else None
    )
    deployment = (
        call_metadata.deployment
        if call_metadata is not None and call_metadata.deployment is not None
        else route.deployment if route is not None else None
    )
    metadata = dict(resolved_context.metadata)
    if route is not None and route.options:
        metadata["route_options"] = route.options
    if call_metadata is not None and call_metadata.raw_metadata:
        metadata["provider_raw_metadata"] = call_metadata.raw_metadata

    return ProviderRequestLogPayload(
        provider=provider,
        operation=operation or resolved_context.purpose or (route.task if route else None),
        model=model,
        deployment=deployment,
        request_id=call_metadata.request_id if call_metadata else None,
        status="error" if error else "ok",
        source_id=resolved_context.source_id,
        conversation_id=resolved_context.conversation_id,
        prompt_id=resolved_context.prompt_id,
        prompt_version=resolved_context.prompt_version,
        schema_id=resolved_context.schema_id,
        schema_version=resolved_context.schema_version,
        privacy_level=resolved_context.privacy_level,
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
        total_tokens=usage.total_tokens if usage else None,
        audio_seconds=usage.audio_seconds if usage else None,
        estimated_cost=usage.estimated_cost if usage else None,
        currency=usage.currency if usage else None,
        latency_ms=call_metadata.latency_ms if call_metadata else None,
        error_code=error.code.value if error else None,
        error_message=error.message if error else None,
        metadata=metadata,
    )
