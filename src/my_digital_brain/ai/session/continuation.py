"""Helpers for resuming sessions after channel-mediated tool interactions."""

from __future__ import annotations

from my_digital_brain.ai.models import ToolResult
from my_digital_brain.ai.schemas import ChatMessage

from .contracts import LLMSessionContinuation


def upsert_tool_result_message(
    messages: list[ChatMessage],
    call_id: str,
    result: ToolResult,
) -> ToolResult:
    """Store one provider tool output per provider-issued call ID.

    A pending channel-mediated result is replaced by its eventual answer. Any
    completed output is authoritative: a replay of its call ID reuses that
    persisted output rather than executing or appending another result.
    """

    matching_indexes = [
        index
        for index, message in enumerate(messages)
        if message.role == "tool" and message.tool_call_id == call_id
    ]
    if matching_indexes:
        existing = _tool_result_from_message(messages[matching_indexes[0]])
        if existing.status != "pending":
            _remove_duplicate_tool_messages(messages, matching_indexes)
            return existing
        messages[matching_indexes[0]] = _tool_message(call_id, result)
        _remove_duplicate_tool_messages(messages, matching_indexes)
        return result
    messages.append(_tool_message(call_id, result))
    return result


def continuation_with_tool_results(
    continuation: LLMSessionContinuation,
    results: dict[str, ToolResult],
) -> LLMSessionContinuation:
    """Append all results for one grouped external interaction."""

    messages = list(continuation.messages)
    expected = {call.call_id for call in continuation.pending_tool_calls}
    supplied = set(results)
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        raise ValueError(f"Tool result group mismatch (missing={missing}, extra={extra}).")
    for call_id, result in results.items():
        upsert_tool_result_message(messages, call_id, result)
    return continuation.model_copy(update={"messages": messages}, deep=True)


def _tool_message(call_id: str, result: ToolResult) -> ChatMessage:
    return ChatMessage(
        role="tool",
        tool_call_id=call_id,
        content=result.model_dump_json(exclude_none=True),
    )


def _tool_result_from_message(message: ChatMessage) -> ToolResult:
    try:
        return ToolResult.model_validate_json(message.content or "{}")
    except (TypeError, ValueError):
        return ToolResult(
            status="error",
            output=message.content or "The persisted tool output was unreadable.",
        )


def _remove_duplicate_tool_messages(
    messages: list[ChatMessage],
    matching_indexes: list[int],
) -> None:
    for index in reversed(matching_indexes[1:]):
        del messages[index]
