"""Bind registered tools to the active parent agentic-state invocation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel

from product.agentic.tools.contracts import RegisteredTool
from product.agentic.tools.models import AgenticToolInvocationContext
from product.ai.ai_clients.protocols.protocol_tools import (
    ToolCallContextDTO,
    ToolInteractionRequestDTO,
)

if TYPE_CHECKING:
    from product.agentic.history import AgenticHistorySession


@dataclass(frozen=True)
class BoundRegisteredTool:
    """Supply backend invocation context without adding it to model tool arguments."""

    registered_tool: RegisteredTool
    history_session: AgenticHistorySession
    parent_state_run_id: str

    def __call__(self, **raw_arguments: object) -> BaseModel | ToolInteractionRequestDTO:
        """Preserve direct invocation for callers that do not own provider call metadata."""
        return self.registered_tool.invoke(**raw_arguments)

    def invoke_for_tool_call(
        self,
        call_context: ToolCallContextDTO,
        **raw_arguments: object,
    ) -> BaseModel | ToolInteractionRequestDTO:
        """Validate model arguments and add the active parent/provider call identity."""
        invocation_context = AgenticToolInvocationContext(
            history_session=self.history_session,
            parent_state_run_id=self.parent_state_run_id,
            parent_provider_call_id=call_context.provider_call_id,
        )
        return self.registered_tool.invoke_with_context(
            invocation_context,
            **raw_arguments,
        )
