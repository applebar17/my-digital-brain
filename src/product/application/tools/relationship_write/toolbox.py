"""Toolbox composition for RelationshipWriteState."""

from product.agentic.tools import RegisteredTool, ToolBox
from product.ai.ai_clients.protocols.protocol_tools import ToolDefinitionDTO
from product.application.references import ReferenceContext
from product.application.tools.relationship_write.handler import RelationshipToolHandler
from product.application.tools.relationship_write.models import RelationshipActionRequestDTO
from product.graph import GraphRelationshipService


def build_relationship_toolbox(
    *,
    owner_id: str,
    service: GraphRelationshipService,
    reference_context: ReferenceContext,
    additional_tools: list[RegisteredTool] | None = None,
) -> ToolBox:
    """Expose one discriminated relationship action plus optional clarification."""
    handler = RelationshipToolHandler(
        owner_id=owner_id,
        service=service,
        reference_context=reference_context,
    )
    return ToolBox(
        "relationship_write",
        [
            RegisteredTool(
                definition=ToolDefinitionDTO(
                    name="write_relationship",
                    description=(
                        "Create or update a supported direct relationship, create or reuse "
                        "a narrative relationship context, or append one meaningful "
                        "time-qualified relationship state."
                    ),
                    input_model=RelationshipActionRequestDTO,
                ),
                handler=handler.execute,
            ),
            *(additional_tools or []),
        ],
    )
