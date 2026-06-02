"""Provider protocols for AI capabilities."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from .models import ToolResult
from .schemas import (
    AIRequestContext,
    ChatRequest,
    ChatResult,
    EmbeddingRequest,
    EmbeddingResult,
    ModelRoute,
    StructuredGenerationRequest,
    StructuredGenerationResult,
    TranscriptionRequest,
    TranscriptionResult,
)
from .tools import ToolBox


@runtime_checkable
class LLMProvider(Protocol):
    provider_name: str

    def generate_chat(self, request: ChatRequest) -> ChatResult:
        """Generate a chat response."""


@runtime_checkable
class ToolCallingLLMProvider(Protocol):
    provider_name: str

    def generate_chat_with_tools(
        self,
        request: ChatRequest,
        *,
        toolbox: ToolBox,
        tools_mapping: dict[str, Callable[..., ToolResult]],
        max_tool_calls: int | None = None,
    ) -> ChatResult:
        """Generate a chat response with provider-managed tool-call looping."""


@runtime_checkable
class StructuredLLMProvider(Protocol):
    provider_name: str

    def generate_structured(
        self,
        request: StructuredGenerationRequest,
    ) -> StructuredGenerationResult:
        """Generate and parse a structured response."""


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
