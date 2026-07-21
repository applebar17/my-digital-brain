"""Fake AI providers for tests and local dry runs."""

from __future__ import annotations

import json
from typing import Any

from ..schemas import (
    ChatMessage,
    EmbeddingRequest,
    EmbeddingResult,
    ProviderCallMetadata,
    ProviderUsage,
    TranscriptionRequest,
    TranscriptionResult,
)
from ..session import (
    LLMCompletionRequest,
    LLMCompletionResult,
    LLMSessionRequest,
    LLMSessionResult,
    LLMSessionRunner,
)


class FakeLLMProvider:
    provider_name = "fake"

    def __init__(
        self,
        *,
        chat_response: str = "ok",
        structured_payload: dict[str, Any] | None = None,
        model: str = "fake-chat-model",
        completion_steps: list[dict[str, Any]] | None = None,
    ) -> None:
        self.chat_response = chat_response
        self.structured_payload = structured_payload or {}
        self.model = model
        self.completion_steps = list(completion_steps or [])

    def run_session(self, request: LLMSessionRequest) -> LLMSessionResult:
        return LLMSessionRunner(self).run(request)

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        step = self.completion_steps.pop(0) if self.completion_steps else {}
        tool_calls = step.get("tool_calls") or []
        content = step.get("content")
        if content is None:
            content = (
                json.dumps(self.structured_payload, ensure_ascii=True)
                if request.response_format
                else self.chat_response
            )
        message = ChatMessage(
            role="assistant",
            content=str(content),
            tool_calls=tool_calls or None,
        )
        return LLMCompletionResult(
            assistant_message=message,
            usage=ProviderUsage(
                input_tokens=sum(
                    _message_token_estimate(message.content) for message in request.messages
                ),
                output_tokens=len(str(content).split()),
            ),
            metadata=ProviderCallMetadata.fake(model=request.model or self.model),
        )


class FakeEmbeddingProvider:
    provider_name = "fake"

    def __init__(self, *, dimensions: int = 3, model: str = "fake-embedding-model") -> None:
        self.dimensions = dimensions
        self.model = model

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        dimensions = request.dimensions or self.dimensions
        embeddings = [
            _deterministic_embedding(text, dimensions=dimensions) for text in request.texts
        ]
        return EmbeddingResult(
            embeddings=embeddings,
            usage=ProviderUsage(input_tokens=sum(len(text.split()) for text in request.texts)),
            metadata=ProviderCallMetadata.fake(model=request.model or self.model),
        )


class FakeSpeechToTextProvider:
    provider_name = "fake"

    def __init__(
        self,
        *,
        text: str = "transcribed text",
        language: str | None = "en",
        model: str = "fake-transcription-model",
    ) -> None:
        self.text = text
        self.language = language
        self.model = model

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        return TranscriptionResult(
            text=self.text,
            language=request.language or self.language,
            usage=ProviderUsage(audio_seconds=0.0),
            metadata=ProviderCallMetadata.fake(model=request.model or self.model),
            raw_response={"audio_path": str(request.audio_path)},
        )


class FakeAIProvider(FakeLLMProvider, FakeEmbeddingProvider, FakeSpeechToTextProvider):
    """Combined fake provider implementing all baseline AI capabilities."""

    provider_name = "fake"

    def __init__(
        self,
        *,
        chat_response: str = "ok",
        structured_payload: dict[str, Any] | None = None,
        transcription_text: str = "transcribed text",
        embedding_dimensions: int = 3,
    ) -> None:
        FakeLLMProvider.__init__(
            self,
            chat_response=chat_response,
            structured_payload=structured_payload,
            completion_steps=None,
        )
        self.transcription_text = transcription_text
        self.embedding_dimensions = embedding_dimensions

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        return FakeEmbeddingProvider(dimensions=self.embedding_dimensions).embed(request)

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        return FakeSpeechToTextProvider(text=self.transcription_text).transcribe(request)


def _deterministic_embedding(text: str, *, dimensions: int) -> list[float]:
    seed = sum(ord(char) for char in text)
    return [float((seed + index) % 997) / 997.0 for index in range(dimensions)]


def _message_token_estimate(content: str | list[dict[str, Any]] | None) -> int:
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content.split())
    return len(str(content).split())
