"""Provider-independent execution of one model-selected tool."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from ..models import ToolError, ToolResult
from .contracts import PendingToolCall, ToolMapping


class ToolExecutor:
    """Invoke mapped tools and normalize every result for the model."""

    def __init__(self, *, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def execute(self, call: PendingToolCall, mapping: ToolMapping) -> ToolResult:
        function = mapping.get(call.name)
        if function is None:
            return ToolResult(
                status="error",
                error=ToolError(
                    message=f"Tool '{call.name}' is not available in this session.",
                    code="tool_not_allowed",
                    retryable=False,
                    hint=f"Allowed tools: {', '.join(sorted(mapping))}",
                ),
            )

        context = getattr(function, "_agentic_execution_context", None)
        previous = (
            getattr(context, "current_tool_call_id", None),
            getattr(context, "current_tool_name", None),
            dict(getattr(context, "current_tool_arguments", {}) or {}),
        )
        if context is not None:
            context.current_tool_call_id = call.call_id
            context.current_tool_name = call.name
            context.current_tool_arguments = dict(call.arguments)
        try:
            output = function(**call.arguments)
            if isinstance(output, ToolResult):
                return output
            if isinstance(output, BaseModel):
                return ToolResult(status="ok", data=output.model_dump(mode="json"))
            if isinstance(output, (dict, list)):
                return ToolResult(status="ok", data=output)
            return ToolResult(status="ok", output="ok" if output is None else str(output))
        except Exception as exc:
            self.logger.exception("LLM tool execution failed: %s", call.name)
            return ToolResult(
                status="error",
                error=ToolError(
                    message=f"Tool '{call.name}' failed: {exc}",
                    code="tool_execution_error",
                    type=exc.__class__.__name__,
                    retryable=False,
                ),
            )
        finally:
            if context is not None:
                context.current_tool_call_id = previous[0]
                context.current_tool_name = previous[1]
                context.current_tool_arguments = previous[2]
