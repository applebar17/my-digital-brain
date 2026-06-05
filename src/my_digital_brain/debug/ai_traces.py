from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import re
from threading import RLock
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


TraceSectionType = Literal["text", "json"]

_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|token|secret|password|authorization|bearer|credential)",
    re.IGNORECASE,
)
_SECRET_TEXT_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization|bearer)"
    r"[\"']?\s*[:=]\s*[\"']?[^\s,;}\"']+"
)
_MAX_TEXT_CHARS = 80_000


class AIFlowTraceSection(BaseModel):
    title: str
    content: str
    content_type: TraceSectionType = "text"


class AIFlowTraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    message_id: str | None = None
    sequence: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    title: str
    call_kind: str
    state_id: str | None = None
    purpose: str | None = None
    model: str | None = None
    provider: str | None = None
    prompt_id: str | None = None
    schema_id: str | None = None
    toolbox_name: str | None = None
    status: str = "ok"
    sections: list[AIFlowTraceSection] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIFlowTraceEventList(BaseModel):
    session_id: str
    events: list[AIFlowTraceEvent]
    latest_sequence: int


class AIFlowTraceStore:
    def __init__(self, *, max_events_per_session: int = 500) -> None:
        self.max_events_per_session = max(1, int(max_events_per_session))
        self._events: dict[str, deque[AIFlowTraceEvent]] = {}
        self._next_sequence: dict[str, int] = {}
        self._lock = RLock()

    def append(self, event: AIFlowTraceEvent) -> AIFlowTraceEvent:
        with self._lock:
            sequence = self._next_sequence.get(event.session_id, 1)
            self._next_sequence[event.session_id] = sequence + 1
            stored = event.model_copy(update={"sequence": sequence}, deep=True)
            events = self._events.setdefault(
                event.session_id,
                deque(maxlen=self.max_events_per_session),
            )
            events.append(stored)
            return stored

    def list(
        self,
        session_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 200,
    ) -> AIFlowTraceEventList:
        with self._lock:
            events = list(self._events.get(session_id, ()))
            filtered = [
                event for event in events if event.sequence > max(0, int(after_sequence))
            ][: max(1, min(int(limit), self.max_events_per_session))]
            latest = self._next_sequence.get(session_id, 1) - 1
        return AIFlowTraceEventList(
            session_id=session_id,
            events=filtered,
            latest_sequence=max(0, latest),
        )

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._events.pop(session_id, None)
            self._next_sequence.pop(session_id, None)


@dataclass(slots=True)
class AIFlowTraceSessionContext:
    session_id: str
    message_id: str | None = None
    current_text: str | None = None
    store: AIFlowTraceStore | None = None


@dataclass(slots=True)
class AIFlowTraceCallContext:
    call_kind: str
    title: str
    state_id: str | None = None
    purpose: str | None = None
    model: str | None = None
    provider: str | None = None
    prompt_id: str | None = None
    schema_id: str | None = None
    toolbox_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


_trace_session: ContextVar[AIFlowTraceSessionContext | None] = ContextVar(
    "ai_flow_trace_session",
    default=None,
)
_trace_call: ContextVar[AIFlowTraceCallContext | None] = ContextVar(
    "ai_flow_trace_call",
    default=None,
)
_trace_store = AIFlowTraceStore()


def get_ai_flow_trace_store() -> AIFlowTraceStore:
    return _trace_store


@contextmanager
def ai_flow_trace_session(
    *,
    session_id: str,
    message_id: str | None,
    current_text: str | None,
    store: AIFlowTraceStore | None = None,
) -> Iterator[None]:
    token = _trace_session.set(
        AIFlowTraceSessionContext(
            session_id=session_id,
            message_id=message_id,
            current_text=current_text,
            store=store or get_ai_flow_trace_store(),
        ),
    )
    try:
        yield
    finally:
        _trace_session.reset(token)


@contextmanager
def ai_flow_trace_call(
    *,
    call_kind: str,
    title: str,
    state_id: str | None = None,
    purpose: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    prompt_id: str | None = None,
    schema_id: str | None = None,
    toolbox_name: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Iterator[None]:
    parent = _trace_call.get()
    merged_metadata = {
        **(parent.metadata if parent is not None else {}),
        **dict(metadata or {}),
    }
    token = _trace_call.set(
        AIFlowTraceCallContext(
            call_kind=call_kind,
            title=title,
            state_id=state_id if state_id is not None else _parent_value(parent, "state_id"),
            purpose=purpose if purpose is not None else _parent_value(parent, "purpose"),
            model=model if model is not None else _parent_value(parent, "model"),
            provider=provider if provider is not None else _parent_value(parent, "provider"),
            prompt_id=prompt_id if prompt_id is not None else _parent_value(parent, "prompt_id"),
            schema_id=schema_id if schema_id is not None else _parent_value(parent, "schema_id"),
            toolbox_name=(
                toolbox_name
                if toolbox_name is not None
                else _parent_value(parent, "toolbox_name")
            ),
            metadata=merged_metadata,
        ),
    )
    try:
        yield
    finally:
        _trace_call.reset(token)


def record_openai_payload(
    params: Mapping[str, Any],
    *,
    status: str = "started",
    metadata: Mapping[str, Any] | None = None,
) -> None:
    messages = list(params.get("messages") or [])
    sections = [
        _section("SYSTEM PROMPT", _system_prompt_from_messages(messages)),
        _json_section("MODEL MESSAGES", _non_system_messages(messages)),
    ]
    expected = _expected_output_payload(params)
    if expected:
        sections.append(_json_section("EXPECTED OUTPUT", expected))
    record_ai_flow_event(
        title=_title("OpenAI Payload"),
        call_kind="openai_payload",
        model=str(params.get("model") or "") or None,
        status=status,
        sections=sections,
        metadata={"param_keys": sorted(params.keys()), **dict(metadata or {})},
    )


def record_openai_response(response: Any, *, metadata: Mapping[str, Any] | None = None) -> None:
    record_ai_flow_event(
        title=_title("OpenAI Response"),
        call_kind="openai_response",
        status="ok",
        sections=[
            _section("LLM OUTPUT", _response_content(response)),
            _json_section("TOOL CALLS", _response_tool_calls(response)),
            _json_section("RAW RESPONSE SUMMARY", _response_summary(response)),
        ],
        metadata=dict(metadata or {}),
    )


def record_provider_result(
    *,
    content: Any,
    call_kind: str,
    title: str,
    status: str = "ok",
    metadata: Mapping[str, Any] | None = None,
) -> None:
    section_title = "PARSED STRUCTURED OUTPUT" if call_kind == "structured" else "LLM OUTPUT"
    section = (
        _json_section(section_title, _model_dump(content))
        if not isinstance(content, str)
        else _section(section_title, content)
    )
    record_ai_flow_event(
        title=_title(title),
        call_kind=f"{call_kind}_result",
        status=status,
        sections=[section],
        metadata=dict(metadata or {}),
    )


def record_embedding_result(
    *,
    texts: Sequence[str],
    count: int,
    model: str | None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    record_ai_flow_event(
        title=_title("Embedding Request"),
        call_kind="embedding",
        model=model,
        sections=[
            _json_section("MODEL INPUTS", list(texts)),
            _section("LLM OUTPUT", f"Generated {count} embedding vector(s)."),
        ],
        metadata=dict(metadata or {}),
    )


def record_tool_execution(
    *,
    tool_name: str,
    arguments: Any,
    output: Any | None = None,
    status: str = "started",
    metadata: Mapping[str, Any] | None = None,
) -> None:
    sections = [_json_section("TOOL CALLS", {"tool_name": tool_name, "arguments": arguments})]
    if output is not None:
        sections.append(_json_section("TOOL OUTPUTS", _model_dump(output)))
    record_ai_flow_event(
        title=_title(f"Tool: {tool_name}"),
        call_kind="tool_execution",
        status=status,
        sections=sections,
        metadata=dict(metadata or {}),
    )


def record_ai_flow_event(
    *,
    title: str,
    call_kind: str,
    sections: Sequence[AIFlowTraceSection],
    status: str = "ok",
    state_id: str | None = None,
    purpose: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    prompt_id: str | None = None,
    schema_id: str | None = None,
    toolbox_name: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    session = _trace_session.get()
    if session is None or session.store is None:
        return
    call = _trace_call.get()
    event = AIFlowTraceEvent(
        session_id=session.session_id,
        message_id=session.message_id,
        title=title,
        call_kind=call_kind,
        state_id=state_id if state_id is not None else _parent_value(call, "state_id"),
        purpose=purpose if purpose is not None else _parent_value(call, "purpose"),
        model=model if model is not None else _parent_value(call, "model"),
        provider=provider if provider is not None else _parent_value(call, "provider"),
        prompt_id=prompt_id if prompt_id is not None else _parent_value(call, "prompt_id"),
        schema_id=schema_id if schema_id is not None else _parent_value(call, "schema_id"),
        toolbox_name=(
            toolbox_name if toolbox_name is not None else _parent_value(call, "toolbox_name")
        ),
        status=status,
        sections=[
            section.model_copy(update={"content": _redact_text(section.content)})
            for section in sections
        ],
        metadata=_sanitize(
            {
                **(call.metadata if call is not None else {}),
                **dict(metadata or {}),
            },
        ),
    )
    session.store.append(event)


def _parent_value(parent: Any, field_name: str) -> str | None:
    if parent is None:
        return None
    value = getattr(parent, field_name, None)
    return str(value) if value not in (None, "") else None


def _title(fallback: str) -> str:
    call = _trace_call.get()
    if call is None:
        return fallback
    prefix = call.state_id or call.purpose or call.title
    return f"{prefix} - {fallback}" if prefix else fallback


def _system_prompt_from_messages(messages: Sequence[Any]) -> str:
    prompts: list[str] = []
    for message in messages:
        if isinstance(message, Mapping) and message.get("role") == "system":
            prompts.append(str(message.get("content") or ""))
    return "\n\n--- system message ---\n\n".join(prompts)


def _non_system_messages(messages: Sequence[Any]) -> list[Any]:
    return [
        _sanitize(message)
        for message in messages
        if not (isinstance(message, Mapping) and message.get("role") == "system")
    ]


def _expected_output_payload(params: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    tools = params.get("tools")
    if tools:
        payload["tools"] = _tool_summaries(tools)
    response_format = params.get("response_format")
    if response_format:
        payload["response_format"] = _sanitize(response_format)
    return payload


def _tool_summaries(tools: Any) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    if not isinstance(tools, Sequence) or isinstance(tools, (str, bytes)):
        return summaries
    for tool in tools:
        data = _model_dump(tool)
        function = data.get("function") if isinstance(data, dict) else None
        if not isinstance(function, dict):
            continue
        summaries.append(
            {
                "name": function.get("name"),
                "description": function.get("description"),
                "parameters": function.get("parameters"),
            },
        )
    return summaries


def _response_content(response: Any) -> str:
    choice = _first_choice(response)
    message = _value(choice, "message")
    return str(_value(message, "content") or "")


def _response_tool_calls(response: Any) -> Any:
    choice = _first_choice(response)
    message = _value(choice, "message")
    return _sanitize(_value(message, "tool_calls") or [])


def _response_summary(response: Any) -> dict[str, Any]:
    choice = _first_choice(response)
    return {
        "id": _value(response, "id"),
        "finish_reason": _value(choice, "finish_reason"),
        "usage": _sanitize(_value(response, "usage")),
    }


def _first_choice(response: Any) -> Any:
    choices = _value(response, "choices") or []
    return choices[0] if choices else {}


def _value(source: Any, key: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


def _section(title: str, content: Any) -> AIFlowTraceSection:
    return AIFlowTraceSection(
        title=title,
        content=_truncate(_redact_text(str(content or ""))),
        content_type="text",
    )


def _json_section(title: str, content: Any) -> AIFlowTraceSection:
    return AIFlowTraceSection(
        title=title,
        content=_to_json(content),
        content_type="json",
    )


def _to_json(value: Any) -> str:
    try:
        text = json.dumps(_sanitize(value), ensure_ascii=False, indent=2, default=str)
    except TypeError:
        text = str(value)
    return _truncate(text)


def _sanitize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _sanitize(value.model_dump(mode="json", exclude_none=True))
    if hasattr(value, "model_dump"):
        try:
            return _sanitize(value.model_dump(exclude_none=True))
        except Exception:
            return str(value)
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _SECRET_KEY_RE.search(key_text):
                clean[key_text] = "[REDACTED]"
            else:
                clean[key_text] = _sanitize(item)
        return clean
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _model_dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(exclude_none=True)
        except Exception:
            return str(value)
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return value


def _redact_text(value: str) -> str:
    return _SECRET_TEXT_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)


def _truncate(value: str) -> str:
    if len(value) <= _MAX_TEXT_CHARS:
        return value
    return f"{value[:_MAX_TEXT_CHARS].rstrip()}\n\n[TRUNCATED]"
