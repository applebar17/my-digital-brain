"""Provider-neutral loop for one logical LLM session."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from ..models import ToolResult
from ..schemas import ChatMessage
from ..structured_schema import strict_response_format
from .contracts import (
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
                pending, remaining, new_events, new_messages = self._execute_batch(
                    request,
                    tool_calls,
                    messages,
                )
                events.extend(new_events)
                messages = new_messages
                executed += len(tool_calls)
                if pending is not None:
                    continuation = LLMSessionContinuation(
                        session_id=session_id,
                        messages=messages,
                        pending_tool_call=pending,
                        remaining_tool_calls=remaining,
                        tool_events=events,
                        tool_calls_used=executed,
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
        if not any(
            message.role == "tool"
            and message.tool_call_id == continuation.pending_tool_call.call_id
            for message in messages
        ):
            return LLMSessionAwaitingTool(
                session_id=session_id,
                messages=messages,
                continuation=continuation,
                tool_events=events,
            )
        executed = continuation.tool_calls_used
        for pending in continuation.remaining_tool_calls:
            tool_call = {
                "id": pending.call_id,
                "function": {
                    "name": pending.name,
                    "arguments": json.dumps(pending.arguments, ensure_ascii=True),
                },
            }
            next_pending, remaining, new_events, messages = self._execute_batch(
                request,
                [tool_call],
                messages,
            )
            events.extend(new_events)
            executed += 1
            if next_pending is not None:
                next_continuation = LLMSessionContinuation(
                    session_id=session_id,
                    messages=messages,
                    pending_tool_call=next_pending,
                    remaining_tool_calls=remaining,
                    tool_events=events,
                    tool_calls_used=executed,
                )
                return LLMSessionAwaitingTool(
                    session_id=session_id,
                    messages=messages,
                    continuation=next_continuation,
                    tool_events=events,
                )

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
        PendingToolCall | None,
        list[PendingToolCall],
        list[ToolExecutionEvent],
        list[ChatMessage],
    ]:
        events: list[ToolExecutionEvent] = []
        remaining: list[PendingToolCall] = []
        for index, raw_call in enumerate(raw_calls):
            pending_call = _pending_tool_call(raw_call)
            result = self.tool_executor.execute(pending_call, request.tools_mapping)
            events.append(
                ToolExecutionEvent(
                    call_id=pending_call.call_id,
                    name=pending_call.name,
                    arguments=pending_call.arguments,
                    result=result,
                )
            )
            if result.status == "pending":
                remaining = [_pending_tool_call(call) for call in raw_calls[index + 1 :]]
                return pending_call, remaining, events, messages
            messages.append(_tool_message(pending_call.call_id, result))
        return None, remaining, events, messages

    def _cap_reached(self, request: LLMSessionRequest, executed: int) -> bool:
        limit = request.max_tool_calls
        return limit is not None and limit >= 0 and executed >= limit

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
