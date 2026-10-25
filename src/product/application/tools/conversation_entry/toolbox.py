"""Toolbox composition for the conversation-entry state."""

from product.agentic.tools import RegisteredTool, ToolBox
from product.ai.ai_clients.protocols.protocol_tools import ToolDefinitionDTO
from product.application.tools.conversation_entry.models import (
    ConversationCapabilityHandler,
    ConversationCapabilityRequestDTO,
)


def build_conversation_entry_toolbox(
    *,
    query_memory: ConversationCapabilityHandler,
    ingest_memory: ConversationCapabilityHandler,
) -> ToolBox:
    """Bind temporary typed contracts to the two accepted root capabilities.

    Dependencies:
        Application composition supplies both executable functions. The
        temporary request/result DTOs are replaced by each capability's real
        contract when `MemoryQueryState` and `MemoryIngestionWorkflow` exist;
        no fake production implementation or fallback behavior is provided.
    """
    return ToolBox(
        "conversation_entry",
        [
            RegisteredTool(
                definition=ToolDefinitionDTO(
                    name="query_memory",
                    description=(
                        "Query retained memory when the user's request depends on previously "
                        "stored personal context."
                    ),
                    input_model=ConversationCapabilityRequestDTO,
                ),
                handler=query_memory,
            ),
            RegisteredTool(
                definition=ToolDefinitionDTO(
                    name="ingest_memory",
                    description=(
                        "Process new, corrected, updated, or otherwise memory-worthy information "
                        "provided by the user."
                    ),
                    input_model=ConversationCapabilityRequestDTO,
                ),
                handler=ingest_memory,
            ),
        ],
    )
