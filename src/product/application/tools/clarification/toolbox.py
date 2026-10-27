"""Registration of the clarification child as a parent-state tool."""

from product.agentic.tools import RegisteredTool
from product.ai.ai_clients.protocols.protocol_tools import ToolDefinitionDTO
from product.application.interactions import InteractionContinuationStore
from product.application.states.clarification import (
    ClarificationRequestDTO,
    ClarificationResultDTO,
    ClarificationState,
)
from product.application.tools.clarification.handler import ClarificationAgentToolHandler


def build_clarification_agent_tool(
    state: ClarificationState,
    continuation_store: InteractionContinuationStore,
) -> tuple[
    RegisteredTool[ClarificationRequestDTO, ClarificationResultDTO],
    ClarificationAgentToolHandler,
]:
    """Bind one clarification child and expose its handler for application resumption."""
    handler = ClarificationAgentToolHandler(state, continuation_store)
    tool = RegisteredTool[ClarificationRequestDTO, ClarificationResultDTO](
        definition=ToolDefinitionDTO(
            name="ask_clarification",
            description=(
                "Delegate one material uncertainty to the clarification child state. Supply a "
                "descriptive clarification_ref, the current goal, bounded context, and the exact "
                "uncertainty; the child may ask the user and returns its interpreted result."
            ),
            input_model=ClarificationRequestDTO,
        ),
        handler=handler,
    )
    return tool, handler

