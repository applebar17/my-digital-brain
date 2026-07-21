"""OpenAI-compatible provider adapter."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from my_digital_brain.debug import (
    ai_flow_trace_call,
    record_embedding_result,
    record_provider_result,
)

from ..client import GenAIClient
from ..client.compatibility import apply_chat_completion_compatibility
from ..client.settings import GenAISettings, get_genai_settings
from ..schemas import (
    ChatMessage,
    EmbeddingRequest,
    EmbeddingResult,
    ProviderCallMetadata,
    ProviderUsage,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionSegment,
)
from ..session import (
    LLMCompletionRequest,
    LLMCompletionResult,
    LLMSessionRequest,
    LLMSessionResult,
    LLMSessionRunner,
)
from ..tracing import traceable


class OpenAIProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        client: GenAIClient | None = None,
        settings: GenAISettings | None = None,
    ) -> None:
        self.settings = settings or get_genai_settings()
        self.client = client or GenAIClient(settings=self.settings)

    @traceable(name="AI Provider Session", run_type="llm")
    def run_session(self, request: LLMSessionRequest) -> LLMSessionResult:
        return LLMSessionRunner(self).run(request)

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        started_at = datetime.now(UTC)
        start = time.monotonic()
        params = self._completion_params(request)
        response = self.client.complete_chat(params)
        latency_ms = int((time.monotonic() - start) * 1000)
        result = LLMCompletionResult(
            assistant_message=_response_message_to_chat_message(response),
            usage=_usage_from_response(response),
            metadata=self._metadata(
                model=params["model"],
                started_at=started_at,
                latency_ms=latency_ms,
                raw_response=response,
            ),
            raw_response=_dump_response(response),
        )
        record_provider_result(
            content=result.assistant_message.content or "",
            call_kind="completion",
            title="Provider Completion Result",
            metadata={"latency_ms": latency_ms},
        )
        return result

    @traceable(name="AI Provider Embeddings", run_type="embedding")
    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        started_at = datetime.now(UTC)
        start = time.monotonic()
        with ai_flow_trace_call(
            call_kind="embedding",
            title="AI Provider Embeddings",
            purpose=request.context.purpose,
            model=request.model or self._default_embedding_model(),
            provider=self.provider_name,
            prompt_id=request.context.prompt_id,
            schema_id=request.context.schema_id,
            metadata=request.context.metadata,
        ):
            embeddings = self.client.embed(
                request.texts,
                model=request.model,
                dimensions=request.dimensions,
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            result = EmbeddingResult(
                embeddings=embeddings,
                usage=ProviderUsage(input_tokens=sum(len(text.split()) for text in request.texts)),
                metadata=self._metadata(
                    model=request.model or self._default_embedding_model(),
                    started_at=started_at,
                    latency_ms=latency_ms,
                ),
            )
            record_embedding_result(
                texts=request.texts,
                count=len(embeddings),
                model=result.metadata.model,
                metadata={"latency_ms": latency_ms},
            )
        return result

    @traceable(name="AI Provider Transcription", run_type="tool")
    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        started_at = datetime.now(UTC)
        start = time.monotonic()
        response = self.client.transcribe_audio(
            request.audio_path,
            model=request.model,
            language=request.language,
            prompt=request.prompt,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        return TranscriptionResult(
            text=_transcription_text(response),
            language=_transcription_language(response) or request.language,
            duration_seconds=_transcription_duration(response),
            segments=_transcription_segments(response),
            usage=_transcription_usage(response),
            metadata=self._metadata(
                model=request.model or self._default_transcription_model(),
                started_at=started_at,
                latency_ms=latency_ms,
                raw_response=response,
            ),
            raw_response=_dump_response(response),
        )

    def _metadata(
        self,
        *,
        model: str | None,
        started_at: datetime,
        latency_ms: int,
        raw_response: Any | None = None,
    ) -> ProviderCallMetadata:
        return ProviderCallMetadata(
            provider=self.provider_name,
            model=model,
            request_id=_response_request_id(raw_response),
            started_at=started_at,
            ended_at=datetime.now(UTC),
            latency_ms=latency_ms,
        )

    def _default_embedding_model(self) -> str:
        if self.settings.is_azure and self.settings.azure_openai_embed_deployment:
            return self.settings.azure_openai_embed_deployment
        return self.settings.openai_embed_model

    def _default_transcription_model(self) -> str:
        if self.settings.is_azure and self.settings.azure_openai_transcription_deployment:
            return self.settings.azure_openai_transcription_deployment
        return self.settings.openai_transcription_model

    def _completion_params(self, request: LLMCompletionRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": request.model or self.settings.chat_model_default,
            "messages": [_chat_message_to_dict(message) for message in request.messages],
        }
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.max_tokens is not None:
            params["max_tokens"] = request.max_tokens
        if request.tools:
            params["tools"] = request.tools
        if request.response_format:
            params["response_format"] = request.response_format
        return apply_chat_completion_compatibility(params)


def _chat_message_to_dict(message: Any) -> dict[str, Any]:
    if hasattr(message, "model_dump"):
        payload = message.model_dump(exclude_none=True)
    elif isinstance(message, dict):
        payload = dict(message)
    else:
        raise TypeError(f"Unsupported chat message type: {type(message)!r}")
    payload.pop("metadata", None)
    return payload


def _chat_message_from_dict(payload: dict[str, Any]) -> ChatMessage:
    return ChatMessage.model_validate(
        {
            key: value
            for key, value in payload.items()
            if key in {"role", "content", "name", "tool_calls", "tool_call_id", "metadata"}
        }
    )


def _response_message_to_chat_message(response: Any) -> ChatMessage:
    choice = _first_choice(response)
    message = _value(choice, "message")
    if isinstance(message, dict):
        payload = {
            "role": message.get("role") or "assistant",
            "content": message.get("content"),
            "tool_calls": message.get("tool_calls"),
        }
    else:
        payload = {
            "role": getattr(message, "role", "assistant") or "assistant",
            "content": getattr(message, "content", None),
            "tool_calls": _tool_calls_to_dict(getattr(message, "tool_calls", None)),
        }
    return _chat_message_from_dict(payload)


def _tool_calls_to_dict(tool_calls: Any) -> Any:
    if tool_calls is None:
        return None
    if not isinstance(tool_calls, list):
        return tool_calls
    serialized: list[dict[str, Any]] = []
    for call in tool_calls:
        if isinstance(call, dict):
            serialized.append(call)
            continue
        function = getattr(call, "function", None)
        serialized.append(
            {
                "id": getattr(call, "id", None),
                "type": getattr(call, "type", "function"),
                "function": {
                    "name": getattr(function, "name", None),
                    "arguments": getattr(function, "arguments", None),
                },
            }
        )
    return serialized


def _first_choice(response: Any) -> Any:
    choices = _value(response, "choices") or []
    return choices[0] if choices else {}


def _usage_from_response(response: Any) -> ProviderUsage | None:
    usage = _value(response, "usage")
    if usage is None:
        return None
    return ProviderUsage(
        input_tokens=_value(usage, "prompt_tokens") or _value(usage, "input_tokens"),
        output_tokens=_value(usage, "completion_tokens") or _value(usage, "output_tokens"),
        total_tokens=_value(usage, "total_tokens"),
    )


def _transcription_text(response: Any) -> str:
    return str(_value(response, "text") or "")


def _transcription_language(response: Any) -> str | None:
    value = _value(response, "language")
    return str(value) if value is not None else None


def _transcription_duration(response: Any) -> float | None:
    value = _value(response, "duration")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _transcription_segments(response: Any) -> list[TranscriptionSegment]:
    segments = _value(response, "segments") or []
    result: list[TranscriptionSegment] = []
    for segment in segments:
        text = str(_value(segment, "text") or "").strip()
        if not text:
            continue
        result.append(
            TranscriptionSegment(
                text=text,
                start_seconds=_float_value(segment, "start"),
                end_seconds=_float_value(segment, "end"),
                confidence=_float_value(segment, "confidence"),
            )
        )
    return result


def _transcription_usage(response: Any) -> ProviderUsage | None:
    duration = _transcription_duration(response)
    return ProviderUsage(audio_seconds=duration) if duration is not None else None


def _response_request_id(response: Any | None) -> str | None:
    if response is None:
        return None
    value = _value(response, "id") or _value(response, "request_id")
    return str(value) if value is not None else None


def _dump_response(response: Any) -> dict[str, Any] | None:
    if response is None:
        return None
    if isinstance(response, dict):
        return response
    if hasattr(response, "model_dump"):
        dumped = response.model_dump(exclude_none=True)
        return dumped if isinstance(dumped, dict) else None
    if hasattr(response, "__dict__"):
        return {key: value for key, value in vars(response).items() if _is_jsonish(value)}
    return None


def _value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _float_value(source: Any, key: str) -> float | None:
    value = _value(source, key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _is_jsonish(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool, list, dict))
