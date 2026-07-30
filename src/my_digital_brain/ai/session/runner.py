"""Provider-neutral loop for one logical LLM session."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from my_digital_brain.clarification.contracts import (
    ClarificationHistoryMessage,
    ClarificationPacket,
)
from my_digital_brain.clarification.interaction import render_clarification_questions
from my_digital_brain.core.ids import new_uuid

from ..models import ToolResult
from ..schemas import ChatMessage
from ..structured_schema import strict_response_format
from .contracts import (
    DEFAULT_MAX_TOOL_CALLS,
    LLMCompletionRequest,
    LLMCompletionResult,
    LLMSessionAwaitingTool,
    LLMSessionCompleted,
    LLMSessionContinuation,
    LLMSessionFailed,
    LLMSessionRequest,
    LLMSessionResult,
    PendingToolCall,
    ToolExecutionEvent,
)
from .tool_executor import ToolExecutor


class LLMCompletionTransport(Protocol):
    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        """Perform one provider request without executing tools."""


class LLMSessionRunner:
    """Run tool calls and provider turns until a final assistant message."""

    def __init__(
        self, transport: LLMCompletionTransport, *, logger: logging.Logger | None = None
    ) -> None:
        self.transport = transport
        self.logger = logger or logging.getLogger(__name__)
        self.tool_executor = ToolExecutor(logger=self.logger)

    def run(self, request: LLMSessionRequest) -> LLMSessionResult:
        session_id = request.session_id or "session-local"
        messages = (
            list(request.messages)
            if request.messages and request.messages[0].role == "system"
            else [ChatMessage(role="system", content=request.system_prompt), *request.messages]
        )
        events: list[ToolExecutionEvent] = []
        if request.continuation is not None:
            return self._resume(request, messages, events)

        return self._run_turns(request, session_id, messages, events, executed=0)

    def _run_turns(
        self,
        request: LLMSessionRequest,
        session_id: str,
        messages: list[ChatMessage],
        events: list[ToolExecutionEvent],
        *,
        executed: int,
    ) -> LLMSessionResult:
        repair_attempted = False
        last_metadata = None
        last_usage = None
        tools_enabled = bool(request.toolbox and request.tools_mapping) and not self._cap_reached(
            request, executed
        )

        while True:
            completion = self.transport.complete(
                self._completion_request(request, messages, tools_enabled),
            )
            last_metadata = completion.metadata
            last_usage = completion.usage
            assistant = completion.assistant_message
            messages.append(assistant)
            tool_calls = list(assistant.tool_calls or [])
            if tool_calls:
                if not request.tools_mapping:
                    return self._failure(
                        session_id,
                        messages,
                        events,
                        "The model returned tool calls but this session has no tool mapping.",
                        last_metadata,
                    )
                pending, pending_interaction, new_events, new_messages = self._execute_batch(
                    request,
                    tool_calls,
                    messages,
                )
                events.extend(new_events)
                messages = new_messages
                executed += len(tool_calls)
                if pending:
                    continuation = LLMSessionContinuation(
                        session_id=session_id,
                        messages=messages,
                        pending_tool_calls=pending,
                        pending_interaction=pending_interaction,
                        tool_events=events,
                        tool_calls_used=executed,
                        metadata=dict(request.metadata),
                    )
                    return LLMSessionAwaitingTool(
                        session_id=session_id,
                        messages=messages,
                        continuation=continuation,
                        tool_events=events,
                        usage=last_usage,
                        metadata=last_metadata,
                    )
                if self._cap_reached(request, executed):
                    tools_enabled = False
                continue

            if request.output_schema is None:
                return LLMSessionCompleted(
                    session_id=session_id,
                    messages=messages,
                    content=assistant.content or "",
                    tool_events=events,
                    usage=last_usage,
                    metadata=last_metadata,
                )

            try:
                parsed = request.output_schema.model_validate_json(assistant.content or "")
            except (ValidationError, ValueError, TypeError) as exc:
                if repair_attempted:
                    return self._failure(
                        session_id,
                        messages,
                        events,
                        f"Structured output remained invalid after one repair attempt: {exc}",
                        last_metadata,
                    )
                repair_attempted = True
                messages.append(
                    ChatMessage(
                        role="user",
                        content=_repair_message(request.output_schema, exc),
                    )
                )
                continue
            return LLMSessionCompleted(
                session_id=session_id,
                messages=messages,
                content=assistant.content or "",
                parsed=parsed,
                tool_events=events,
                usage=last_usage,
                metadata=last_metadata,
            )

    def _resume(
        self,
        request: LLMSessionRequest,
        messages: list[ChatMessage],
        events: list[ToolExecutionEvent],
    ) -> LLMSessionResult:
        continuation = request.continuation
        assert continuation is not None
        session_id = request.session_id or continuation.session_id
        messages = list(request.messages or continuation.messages)
        events = list(continuation.tool_events)
        pending_ids = {call.call_id for call in continuation.pending_tool_calls}
        completed_ids = {
            message.tool_call_id
            for message in messages
            if message.role == "tool"
            and message.tool_call_id in pending_ids
            and not _tool_message_is_pending(message)
        }
        if completed_ids != pending_ids:
            return LLMSessionAwaitingTool(
                session_id=session_id,
                messages=messages,
                continuation=continuation,
                tool_events=events,
            )
        executed = continuation.tool_calls_used
        resumed_request = request.model_copy(
            update={"continuation": None, "session_id": session_id}
        )
        return self._run_turns(
            resumed_request,
            session_id,
            messages,
            events,
            executed=executed,
        )

    def _completion_request(
        self,
        request: LLMSessionRequest,
        messages: list[ChatMessage],
        tools_enabled: bool,
    ) -> LLMCompletionRequest:
        return LLMCompletionRequest(
            messages=messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            tools=request.toolbox.tools if tools_enabled and request.toolbox else [],
            response_format=(
                strict_response_format(request.output_schema)
                if request.output_schema is not None
                else None
            ),
            context=request.context,
            metadata=request.metadata,
        )

    def _execute_batch(
        self,
        request: LLMSessionRequest,
        raw_calls: list[Any],
        messages: list[ChatMessage],
    ) -> tuple[
        list[PendingToolCall],
        dict[str, Any],
        list[ToolExecutionEvent],
        list[ChatMessage],
    ]:
        events: list[ToolExecutionEvent] = []
        pending_calls: list[PendingToolCall] = []
        pending_events: list[ToolExecutionEvent] = []
        for raw_call in raw_calls:
            pending_call = _pending_tool_call(raw_call)
            result = self.tool_executor.execute(pending_call, request.tools_mapping)
            event = ToolExecutionEvent(
                call_id=pending_call.call_id,
                name=pending_call.name,
                arguments=pending_call.arguments,
                result=result,
            )
            events.append(event)
            if result.status == "pending":
                pending_calls.append(pending_call)
                pending_events.append(event)
            _upsert_tool_message(messages, pending_call.call_id, result)
        if _question_batch_overflow(pending_events):
            message = (
                "This assistant turn requested more than five clarification questions. "
                "No question was discarded; split the questions across later turns."
            )
            details = {
                "requested_question_count": len(pending_events),
                "tool_call_ids": [call.call_id for call in pending_calls],
            }
            for event in pending_events:
                event.result = ToolResult(
                    status="error",
                    output=message,
                    error={
                        "code": "clarification_packet_limit_exceeded",
                        "message": message,
                        "hint": "Retry with at most five questioning tool calls in this turn.",
                        "retryable": True,
                        "details": details,
                    },
                )
                _upsert_tool_message(messages, event.call_id, event.result)
            return [], {}, events, messages

        interaction = {
            "tool_call_ids": [call.call_id for call in pending_calls],
            "results": [
                event.result.model_dump(mode="json", exclude_none=True) for event in pending_events
            ],
        }
        packet = _combined_clarification_packet(pending_events)
        if packet is not None:
            interaction["clarification_packet"] = packet
            for event in pending_events:
                event.result.data = {
                    **(event.result.data or {}),
                    "clarification_packet": packet,
                    "tool_call_ids": [call.call_id for call in pending_calls],
                }
                _upsert_tool_message(messages, event.call_id, event.result)
        return pending_calls, interaction, events, messages

    def _cap_reached(self, request: LLMSessionRequest, executed: int) -> bool:
        limit = request.max_tool_calls
        if limit is None:
            limit = DEFAULT_MAX_TOOL_CALLS
        return limit >= 0 and executed >= limit

    def _failure(
        self,
        session_id: str,
        messages: list[ChatMessage],
        events: list[ToolExecutionEvent],
        error: str,
        metadata: Any,
    ) -> LLMSessionFailed:
        return LLMSessionFailed(
            session_id=session_id,
            messages=messages,
            error=error,
            tool_events=events,
            metadata=metadata,
        )


def _pending_tool_call(raw_call: Any) -> PendingToolCall:
    if isinstance(raw_call, dict):
        function = raw_call.get("function") or {}
        call_id = str(raw_call.get("id") or "unknown-call")
        name = str(function.get("name") or "unknown_tool")
        raw_arguments = function.get("arguments") or "{}"
    else:
        function = getattr(raw_call, "function", None)
        call_id = str(getattr(raw_call, "id", None) or "unknown-call")
        name = str(getattr(function, "name", None) or "unknown_tool")
        raw_arguments = getattr(function, "arguments", None) or "{}"
    try:
        arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
    except json.JSONDecodeError:
        arguments = {}
    return PendingToolCall(
        call_id=call_id,
        name=name,
        arguments=arguments if isinstance(arguments, dict) else {},
    )


def _tool_message(call_id: str, result: ToolResult) -> ChatMessage:
    return ChatMessage(
        role="tool",
        tool_call_id=call_id,
        content=result.model_dump_json(exclude_none=True),
    )


def _tool_message_is_pending(message: ChatMessage) -> bool:
    try:
        payload = json.loads(message.content or "{}")
    except (TypeError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and payload.get("status") == "pending"


def _question_batch_overflow(events: list[ToolExecutionEvent]) -> bool:
    return (
        sum(
            1
            for event in events
            if isinstance(event.result.data, dict)
            and event.result.data.get("interaction_group") == "clarification_questions"
        )
        > 5
    )


def _combined_clarification_packet(
    events: list[ToolExecutionEvent],
) -> dict[str, Any] | None:
    packets: list[ClarificationPacket] = []
    for event in events:
        raw = event.result.data if isinstance(event.result.data, dict) else {}
        packet = raw.get("clarification_packet")
        if packet is None:
            continue
        packets.append(ClarificationPacket.model_validate(packet))
    if not packets:
        return None
    first = packets[0]
    combined = first.model_copy(
        update={
            "packet_id": new_uuid(),
            "tool_call_id": (
                first.tool_call_id if len(packets) == 1 else f"clarification-group-{new_uuid()}"
            ),
            "tool_name": "clarification_questions",
            "questions": [question for packet in packets for question in packet.questions],
            "target_refs": list(
                dict.fromkeys(ref for packet in packets for ref in packet.target_refs)
            ),
            "history_delta": [],
        },
        deep=True,
    )
    combined.history_delta = [
        ClarificationHistoryMessage(
            role="assistant",
            content=render_clarification_questions(combined),
        )
    ]
    return combined.model_dump(mode="json", exclude_none=True)


def _upsert_tool_message(
    messages: list[ChatMessage],
    call_id: str,
    result: ToolResult,
) -> None:
    replacement = _tool_message(call_id, result)
    for index, message in enumerate(messages):
        if message.role == "tool" and message.tool_call_id == call_id:
            messages[index] = replacement
            return
    messages.append(replacement)


def _repair_message(schema: type[BaseModel], exc: Exception) -> str:
    errors = exc.errors() if isinstance(exc, ValidationError) else [{"message": str(exc)}]
    compact = [
        {
            "path": ".".join(str(part) for part in error.get("loc", ())),
            "message": error.get("msg"),
            "type": error.get("type"),
        }
        for error in errors[:12]
    ]
    return (
        f"Repair your previous response for schema {schema.__name__}. Preserve the intent "
        "and correct only the validation errors below. Return only the requested "
        "structured output.\n" + json.dumps(compact, ensure_ascii=True)
    )
