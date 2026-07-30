"""Helpers for resuming sessions after channel-mediated tool interactions."""

from __future__ import annotations

from my_digital_brain.ai.models import ToolResult
from my_digital_brain.ai.schemas import ChatMessage

from .contracts import LLMSessionContinuation


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
        tool_message = ChatMessage(
            role="tool",
            tool_call_id=call_id,
            content=result.model_dump_json(exclude_none=True),
        )
        for index, message in enumerate(messages):
            if message.role == "tool" and message.tool_call_id == call_id:
                messages[index] = tool_message
                break
        else:
            messages.append(tool_message)
    return continuation.model_copy(update={"messages": messages}, deep=True)
