"""Provider-neutral AI request and result schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class AIRequestContext(BaseModel):
    """Cross-cutting metadata carried with provider calls."""

    purpose: str | None = None
    source_id: str | None = None
    conversation_id: str | None = None
    prompt_id: str | None = None
    prompt_version: str | None = None
    schema_id: str | None = None
    schema_version: str | None = None
    privacy_level: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    audio_seconds: float | None = None
    estimated_cost: float | None = None
    currency: str | None = None


class ProviderCallMetadata(BaseModel):
    provider: str
    model: str | None = None
    deployment: str | None = None
    request_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    latency_ms: int | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def fake(cls, *, model: str | None = None) -> ProviderCallMetadata:
        now = datetime.now(UTC)
        return cls(
            provider="fake",
            model=model or "fake-model",
            started_at=now,
            ended_at=now,
            latency_ms=0,
        )


class ModelRoute(BaseModel):
    task: str
    provider: str
    model: str | None = None
    deployment: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Literal["system", "developer", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmbeddingRequest(BaseModel):
    texts: list[str]
    model: str | None = None
    dimensions: int | None = None
    context: AIRequestContext = Field(default_factory=AIRequestContext)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmbeddingResult(BaseModel):
    embeddings: list[list[float]]
    usage: ProviderUsage | None = None
    metadata: ProviderCallMetadata


class TranscriptionSegment(BaseModel):
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TranscriptionRequest(BaseModel):
    audio_path: Path
    model: str | None = None
    language: str | None = None
    prompt: str | None = None
    context: AIRequestContext = Field(default_factory=AIRequestContext)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TranscriptionResult(BaseModel):
    text: str
    language: str | None = None
    duration_seconds: float | None = None
    segments: list[TranscriptionSegment] = Field(default_factory=list)
    usage: ProviderUsage | None = None
    metadata: ProviderCallMetadata
    raw_response: dict[str, Any] | None = None
