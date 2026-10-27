"""Toolbox composition for the conversation-entry state."""

from product.agentic.tools import RegisteredTool, ToolBox
from product.ai.ai_clients.protocols.protocol_tools import ToolDefinitionDTO
from product.application.states.memory_query import MemoryQueryRequestDTO, MemoryQueryState
from product.application.tools.conversation_entry.handlers import MemoryQueryAgentToolHandler
from product.application.tools.conversation_entry.models import (
    IngestMemoryHandler,
    IngestMemoryRequestDTO,
)


def build_conversation_entry_toolbox(
    *,
    memory_query_state: MemoryQueryState,
    ingest_memory: IngestMemoryHandler,
) -> ToolBox:
    """Bind the concrete query state and temporary ingestion capability.

    Dependencies:
        `MemoryQueryAgentToolHandler` adapts the child state's validated result
        without creating another LLM loop. Application composition supplies the
        temporary ingestion handler until `MemoryIngestionWorkflow` replaces it.
    """
    query_memory = MemoryQueryAgentToolHandler(memory_query_state)
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
                    input_model=MemoryQueryRequestDTO,
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
                    input_model=IngestMemoryRequestDTO,
                ),
                handler=ingest_memory,
            ),
        ],
    )
