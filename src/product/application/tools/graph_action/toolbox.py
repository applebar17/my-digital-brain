"""State-specific graph-action registration for one candidate batch."""

from product.agentic.tools import RegisteredTool, ToolBox
from product.ai.ai_clients.protocols.protocol_tools import ToolDefinitionDTO
from product.application.references import ReferenceContext
from product.application.states.ingestion.node_resolution.models import NodeCandidateBatchDTO
from product.application.tools.graph_action.handler import GraphActionToolHandler
from product.application.tools.graph_action.models import (
    graph_action_input_model,
)
from product.graph import GRAPH_LABEL_BY_NODE_TYPE, GraphNodeService


def build_graph_action_tool(
    *,
    owner_id: str,
    service: GraphNodeService,
    reference_context: ReferenceContext,
    batch: NodeCandidateBatchDTO,
) -> RegisteredTool:
    """Build one graph-action schema narrowed to the current batch's node types."""
    input_model = graph_action_input_model(batch.node_types)
    handler = GraphActionToolHandler(
        owner_id=owner_id,
        service=service,
        reference_context=reference_context,
        candidate_types={
            item.candidate_ref: GRAPH_LABEL_BY_NODE_TYPE[item.candidate.node_type]
            for item in batch.candidates
        },
    )
    return RegisteredTool(
        definition=ToolDefinitionDTO(
            name="write_graph_node",
            description=(
                "Create a distinct candidate node or explicitly update a supplied existing "
                "node through the typed action variant matching the candidate type."
            ),
            input_model=input_model,
        ),
        handler=handler.execute,
    )


def build_node_resolution_toolbox(
    *,
    owner_id: str,
    service: GraphNodeService,
    reference_context: ReferenceContext,
    batch: NodeCandidateBatchDTO,
    additional_tools: list[RegisteredTool] | None = None,
) -> ToolBox:
    """Compose the graph action and optional child-state tools for one batch."""
    tools = [
        build_graph_action_tool(
            owner_id=owner_id,
            service=service,
            reference_context=reference_context,
            batch=batch,
        ),
        *(additional_tools or []),
    ]
    return ToolBox("node_resolution", tools)
