"""Helpers for resuming sessions after channel-mediated tool interactions."""

from __future__ import annotations

from my_digital_brain.ai.models import ToolResult
from my_digital_brain.ai.schemas import ChatMessage

from .contracts import LLMSessionContinuation


def continuation_with_tool_result(
    continuation: LLMSessionContinuation,
    result: ToolResult,
) -> LLMSessionContinuation:
    """Append an external tool result to the active session transcript."""

    messages = list(continuation.messages)
    tool_message = ChatMessage(
        role="tool",
        tool_call_id=continuation.pending_tool_call.call_id,
        content=result.model_dump_json(exclude_none=True),
    )
    for index, message in enumerate(messages):
        if message.role == "tool" and message.tool_call_id == tool_message.tool_call_id:
            messages[index] = tool_message
            break
    else:
        messages.append(tool_message)
    return continuation.model_copy(update={"messages": messages}, deep=True)
