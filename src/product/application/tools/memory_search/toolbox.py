"""Registration and toolbox composition for deterministic memory search."""

from product.agentic.tools import RegisteredTool, ToolBox
from product.ai.ai_clients.protocols.protocol_tools import ToolDefinitionDTO
from product.application.memory_search import MemorySearchService
from product.application.references import ReferenceContext
from product.application.tools.memory_search.handler import MemorySearchToolHandler
from product.application.tools.memory_search.models import (
    MemorySearchToolInputDTO,
    MemorySearchToolResultDTO,
)


def build_memory_search_tool(
    *,
    owner_id: str,
    service: MemorySearchService,
    reference_context: ReferenceContext,
) -> RegisteredTool[MemorySearchToolInputDTO, MemorySearchToolResultDTO]:
    """Bind one shared owner, search service, and reference context to `search_memory`."""
    handler = MemorySearchToolHandler(
        owner_id=owner_id,
        service=service,
        reference_context=reference_context,
    )
    return RegisteredTool(
        definition=ToolDefinitionDTO(
            name="search_memory",
            description=(
                "Search retained memory using a semantic query, deterministic filters, active "
                "object references, or a combination of these, then return bounded graph context."
            ),
            input_model=MemorySearchToolInputDTO,
        ),
        handler=handler.search_memory,
    )


def build_memory_search_toolbox(
    *,
    owner_id: str,
    service: MemorySearchService,
    reference_context: ReferenceContext,
) -> ToolBox:
    """Create the minimal reusable toolbox containing only `search_memory`."""
    return ToolBox(
        "memory_search",
        [
            build_memory_search_tool(
                owner_id=owner_id,
                service=service,
                reference_context=reference_context,
            )
        ],
    )
