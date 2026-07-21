"""Provider protocols for AI capabilities."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .schemas import (
    AIRequestContext,
    EmbeddingRequest,
    EmbeddingResult,
    ModelRoute,
    TranscriptionRequest,
    TranscriptionResult,
)
from .session import LLMSessionRequest, LLMSessionResult


@runtime_checkable
class LLMProvider(Protocol):
    provider_name: str

    def run_session(self, request: LLMSessionRequest) -> LLMSessionResult:
        """Run one text or structured LLM session with optional tools."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    provider_name: str

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        """Create embeddings for one or more texts."""


@runtime_checkable
class SpeechToTextProvider(Protocol):
    provider_name: str

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        """Transcribe an audio file into text."""


@runtime_checkable
class ModelRouter(Protocol):
    def route(
        self,
        task: str,
        context: AIRequestContext | None = None,
    ) -> ModelRoute:
        """Resolve a provider/model route for a task."""
