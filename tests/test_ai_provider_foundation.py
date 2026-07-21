from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from my_digital_brain.ai.provider_errors import (
    ProviderError,
    ProviderErrorCode,
    normalize_provider_exception,
)
from my_digital_brain.ai.protocols import (
    EmbeddingProvider,
    LLMProvider,
    SpeechToTextProvider,
)
from my_digital_brain.ai.providers import FakeAIProvider
from my_digital_brain.ai.request_log import build_provider_request_log_payload
from my_digital_brain.ai.schemas import (
    AIRequestContext,
    ChatMessage,
    EmbeddingRequest,
    ModelRoute,
    ProviderCallMetadata,
    ProviderUsage,
    TranscriptionRequest,
)
from my_digital_brain.ai.session import LLMSessionCompleted, LLMSessionRequest


class ExampleStructuredOutput(BaseModel):
    title: str
    importance: int


class ProviderException(Exception):
    status_code = 429
    body = '{"error":{"code":"rate_limit_exceeded","type":"rate_limit_error"}}'


def test_ai_provider_schemas_validate_minimal_and_rich_payloads(tmp_path: Path) -> None:
    context = AIRequestContext(
        purpose="structured_extraction",
        source_id="source-1",
        prompt_id="prompt.memory_extract",
        prompt_version="v1",
        schema_id="schema.memory_extract",
        schema_version="v1",
        privacy_level="private",
        metadata={"trace": "test"},
    )

    session_request = LLMSessionRequest(
        system_prompt="Extract a structured payload.",
        messages=[ChatMessage(role="user", content="I met Marco yesterday.")],
        model="fake-chat-model",
        output_schema=ExampleStructuredOutput,
        context=context,
    )
    transcription_request = TranscriptionRequest(
        audio_path=tmp_path / "voice.ogg",
        language="it",
        context=context,
    )

    assert session_request.context.source_id == "source-1"
    assert session_request.output_schema is ExampleStructuredOutput
    assert transcription_request.audio_path.name == "voice.ogg"


def test_fake_provider_implements_all_provider_protocols(tmp_path: Path) -> None:
    provider = FakeAIProvider(
        chat_response="stored",
        structured_payload={"title": "Memory", "importance": 2},
        transcription_text="I met Marco yesterday.",
        embedding_dimensions=4,
    )

    assert isinstance(provider, LLMProvider)
    assert isinstance(provider, EmbeddingProvider)
    assert isinstance(provider, SpeechToTextProvider)

    session = provider.run_session(
        LLMSessionRequest(
            system_prompt="Extract.",
            messages=[ChatMessage(role="user", content="Memory")],
            output_schema=ExampleStructuredOutput,
        )
    )
    embeddings = provider.embed(EmbeddingRequest(texts=["alpha", "beta"], dimensions=4))
    transcript = provider.transcribe(
        TranscriptionRequest(audio_path=tmp_path / "voice.ogg")
    )

    assert isinstance(session, LLMSessionCompleted)
    assert session.parsed.title == "Memory"
    assert len(embeddings.embeddings) == 2
    assert len(embeddings.embeddings[0]) == 4
    assert transcript.text == "I met Marco yesterday."


def test_provider_error_normalization_maps_rate_limits() -> None:
    error = normalize_provider_exception(ProviderException("rate limit exceeded"))

    assert error.code == ProviderErrorCode.RATE_LIMITED
    assert error.retryable is True
    assert error.provider_status == 429


def test_provider_request_log_payload_is_serializable() -> None:
    context = AIRequestContext(
        purpose="speech_to_text",
        source_id="source-voice-1",
        privacy_level="private",
        metadata={"channel": "telegram"},
    )
    route = ModelRoute(
        task="speech_to_text",
        provider="fake",
        model="fake-transcription-model",
    )
    call_metadata = ProviderCallMetadata.fake(model="fake-transcription-model")
    usage = ProviderUsage(audio_seconds=12.5)

    payload = build_provider_request_log_payload(
        context=context,
        route=route,
        call_metadata=call_metadata,
        usage=usage,
    )
    dumped = payload.model_dump(mode="json", exclude_none=True)

    assert dumped["provider"] == "fake"
    assert dumped["operation"] == "speech_to_text"
    assert dumped["source_id"] == "source-voice-1"
    assert dumped["audio_seconds"] == 12.5
    assert dumped["metadata"] == {"channel": "telegram"}


def test_provider_request_log_payload_can_include_error() -> None:
    error = ProviderError(
        code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
        message="provider unavailable",
        retryable=True,
    )

    payload = build_provider_request_log_payload(
        route=ModelRoute(task="default_chat", provider="fake", model="fake-model"),
        error=error,
    )

    assert payload.status == "error"
    assert payload.error_code == "provider_unavailable"
