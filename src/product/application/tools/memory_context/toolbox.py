"""Toolbox composition for MemoryContextWriteState."""

from product.agentic.tools import RegisteredTool, ToolBox
from product.ai.ai_clients.protocols.protocol_tools import ToolDefinitionDTO
from product.application.references import ReferenceContext
from product.application.tools.memory_context.handler import MemoryContextToolHandler
from product.application.tools.memory_context.models import (
    CreateMemoryLogDTO,
    CreatePerceptionDTO,
)
from product.graph import GraphMemoryService


def build_memory_context_toolbox(
    *,
    owner_id: str,
    service: GraphMemoryService,
    reference_context: ReferenceContext,
    additional_tools: list[RegisteredTool] | None = None,
) -> ToolBox:
    """Expose explicit memory and perception writes plus optional clarification."""
    handler = MemoryContextToolHandler(
        owner_id=owner_id,
        service=service,
        reference_context=reference_context,
    )
    return ToolBox(
        "memory_context_write",
        [
            RegisteredTool(
                definition=ToolDefinitionDTO(
                    name="create_memory_log",
                    description=(
                        "Create one concise additive memory atom linked to supplied resolved "
                        "node references."
                    ),
                    input_model=CreateMemoryLogDTO,
                ),
                handler=handler.create_memory_log,
            ),
            RegisteredTool(
                definition=ToolDefinitionDTO(
                    name="create_perception",
                    description=(
                        "Create one source-grounded subjective perception attached to a "
                        "supplied resolved node reference."
                    ),
                    input_model=CreatePerceptionDTO,
                ),
                handler=handler.create_perception,
            ),
            *(additional_tools or []),
        ],
    )
