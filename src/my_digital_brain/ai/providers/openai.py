"""OpenAI-compatible provider adapter."""

from __future__ import annotations

from datetime import UTC, datetime
import time
from collections.abc import Callable
from typing import Any

from ..client import GenAIClient
from ..client.settings import GenAISettings, get_genai_settings
from ..models import ToolResult
from ..schemas import (
    ChatRequest,
    ChatResult,
    EmbeddingRequest,
    EmbeddingResult,
    ProviderCallMetadata,
    ProviderUsage,
    StructuredGenerationRequest,
    StructuredGenerationResult,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionSegment,
)
from ..tools import ToolBox
from ..client.compatibility import apply_chat_completion_compatibility
from ..tracing import traceable
from my_digital_brain.debug import (
    ai_flow_trace_call,
    record_embedding_result,
    record_provider_result,
)


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

    @traceable(name="AI Provider Chat", run_type="llm")
    def generate_chat(self, request: ChatRequest) -> ChatResult:
        started_at = datetime.now(UTC)
        start = time.monotonic()
        params = self._chat_params(request)

        with self._trace_call_context(
            "chat",
            request,
            model=params["model"],
            title="AI Provider Chat",
        ):
            response = self.client.call_openai(params)
            latency_ms = int((time.monotonic() - start) * 1000)
            result = ChatResult(
                content=_response_content(response),
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
                content=result.content,
                call_kind="chat",
                title="Provider Chat Result",
                metadata={"latency_ms": latency_ms},
            )
        return result

    @traceable(name="AI Provider Chat With Tools", run_type="llm")
    def generate_chat_with_tools(
        self,
        request: ChatRequest,
        *,
        toolbox: ToolBox,
        tools_mapping: dict[str, Callable[..., ToolResult]],
        max_tool_calls: int | None = None,
    ) -> ChatResult:
        started_at = datetime.now(UTC)
        start = time.monotonic()
        params = self._chat_params(request)

        with self._trace_call_context(
            "chat_with_tools",
            request,
            model=params["model"],
            title="AI Provider Chat With Tools",
            toolbox_name=toolbox.name,
            metadata={"max_tool_calls": max_tool_calls},
        ):
            response = self.client.call_openai(
                params,
                tools_mapping=tools_mapping,
                toolbox=toolbox,
                max_tool_calls=max_tool_calls,
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            result = ChatResult(
                content=_response_content(response),
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
                content=result.content,
                call_kind="chat_with_tools",
                title="Provider Chat With Tools Result",
                metadata={"latency_ms": latency_ms, "toolbox_name": toolbox.name},
            )
        return result

    @traceable(name="AI Provider Structured Generation", run_type="parser")
    def generate_structured(
        self,
        request: StructuredGenerationRequest,
    ) -> StructuredGenerationResult:
        started_at = datetime.now(UTC)
        start = time.monotonic()
        with self._trace_structured_context(request):
            messages = (
                [_chat_message_to_dict(message) for message in request.messages]
                if request.messages
                else None
            )
            parsed = self.client.generate_structured(
                request.output_schema,
                request.system_prompt,
                request.input_message,
                messages=messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            latency_ms = int((time.monotonic() - start) * 1000)
            result = StructuredGenerationResult(
                parsed=parsed,
                metadata=self._metadata(
                    model=request.model or self.settings.chat_model_default,
                    started_at=started_at,
                    latency_ms=latency_ms,
                ),
            )
            record_provider_result(
                content=parsed,
                call_kind="structured",
                title=f"Structured Result: {request.output_schema.__name__}",
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
        if (
            self.settings.is_azure
            and self.settings.azure_openai_transcription_deployment
        ):
            return self.settings.azure_openai_transcription_deployment
        return self.settings.openai_transcription_model

    def _chat_params(self, request: ChatRequest) -> dict[str, Any]:
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
        return apply_chat_completion_compatibility(params)

    def _trace_call_context(
        self,
        call_kind: str,
        request: ChatRequest,
        *,
        model: str,
        title: str,
        toolbox_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        return ai_flow_trace_call(
            call_kind=call_kind,
            title=title,
            state_id=_state_id_from_request_context(request.context),
            purpose=request.context.purpose,
            model=model,
            provider=self.provider_name,
            prompt_id=request.context.prompt_id,
            schema_id=request.context.schema_id,
            toolbox_name=toolbox_name,
            metadata={
                **request.context.metadata,
                **request.metadata,
                **(metadata or {}),
            },
        )

    def _trace_structured_context(self, request: StructuredGenerationRequest):
        return ai_flow_trace_call(
            call_kind="structured",
            title=f"AI Provider Structured: {request.output_schema.__name__}",
            state_id=_state_id_from_request_context(request.context),
            purpose=request.context.purpose,
            model=request.model or self.settings.chat_model_default,
            provider=self.provider_name,
            prompt_id=request.context.prompt_id,
            schema_id=request.context.schema_id or request.output_schema.__name__,
            metadata={
                **request.context.metadata,
                **request.metadata,
                "output_schema": request.output_schema.__name__,
            },
        )


def _chat_message_to_dict(message: Any) -> dict[str, Any]:
    if hasattr(message, "model_dump"):
        payload = message.model_dump(exclude_none=True)
    elif isinstance(message, dict):
        payload = dict(message)
    else:
        raise TypeError(f"Unsupported chat message type: {type(message)!r}")
    payload.pop("metadata", None)
    return payload


def _state_id_from_request_context(context: Any) -> str | None:
    metadata = getattr(context, "metadata", None)
    if isinstance(metadata, dict) and metadata.get("state_id"):
        return str(metadata["state_id"])
    return None


def _response_content(response: Any) -> str:
    choice = _first_choice(response)
    message = getattr(choice, "message", None)
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")


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
        return {
            key: value
            for key, value in vars(response).items()
            if _is_jsonish(value)
        }
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
