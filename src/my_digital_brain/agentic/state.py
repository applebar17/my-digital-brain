from __future__ import annotations

from pydantic import Field

from my_digital_brain.agentic.base import AgenticModel
from my_digital_brain.agentic.enums import AgenticNodeKind, AgenticStateId


class AgenticStateConfig(AgenticModel):
    state_id: AgenticStateId
    node_kind: AgenticNodeKind = AgenticNodeKind.AGENTIC_STATE
    purpose: str
    prompt_id: str
    prompt_version: str = "v1"
    required_context_type: str
    produced_context_type: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    handoff_targets: list[str] = Field(default_factory=list)
    max_tool_calls: int = Field(default=3, ge=0)
    model_task: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


def default_state_configs() -> dict[AgenticStateId, AgenticStateConfig]:
    return {
        AgenticStateId.CONVERSATION_ENTRY: AgenticStateConfig(
            state_id=AgenticStateId.CONVERSATION_ENTRY,
            purpose="Choose whether to answer directly or call a top-level memory tool.",
            prompt_id="conversation_entry",
            required_context_type="ConversationContext",
            produced_context_type="ToolResultContext",
            allowed_tools=[
                "start_memory_ingestion",
                "query_memory_context",
                "update_memory_graph",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "raw_graph_query",
                "focused_extraction",
            ],
            handoff_targets=[
                "memory_query",
                "graph_update",
            ],
            model_task="conversation_entry",
        ),
        AgenticStateId.REASONING_CHECKPOINT: AgenticStateConfig(
            state_id=AgenticStateId.REASONING_CHECKPOINT,
            purpose=(
                "Augment process context with structured reasoning insights before "
                "a downstream storage, validation, or orchestration step."
            ),
            prompt_id="reasoning_checkpoint",
            required_context_type="ReasoningCheckpointContext",
            produced_context_type="ReasoningCheckpointResultContext",
            allowed_tools=[
                "get_context_package",
                "get_entity_detail",
                "get_neighborhood_view",
                "get_target_evidence",
                "request_user_clarification",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "start_memory_ingestion",
                "update_memory_graph",
                "raw_graph_query",
                "focused_extraction",
            ],
            handoff_targets=[
                "entity_ingestion_planning",
                "relationship_ingestion_planning",
                "focused_extraction_planning",
                "validation_resolution",
                "clarification_waiting",
            ],
            max_tool_calls=2,
            model_task="reasoning_checkpoint",
        ),
        AgenticStateId.PLANNING_CHECKPOINT: AgenticStateConfig(
            state_id=AgenticStateId.PLANNING_CHECKPOINT,
            purpose=(
                "Convert caller-provided goals, context, and reasoning artifacts into "
                "ordered structured process actions without mutating storage."
            ),
            prompt_id="planning_checkpoint",
            required_context_type="PlanningTransformContext",
            produced_context_type="PlanningTransformResultContext",
            allowed_tools=[
                "get_context_package",
                "get_entity_detail",
                "get_neighborhood_view",
                "get_target_evidence",
                "request_user_clarification",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "start_memory_ingestion",
                "update_memory_graph",
                "raw_graph_query",
                "focused_extraction",
            ],
            handoff_targets=[
                "entity_ingestion_planning",
                "relationship_ingestion_planning",
                "missing_entity_planning",
                "clarification_waiting",
            ],
            max_tool_calls=2,
            model_task="planning_checkpoint",
        ),
        AgenticStateId.MEMORY_QUERY: AgenticStateConfig(
            state_id=AgenticStateId.MEMORY_QUERY,
            purpose="Retrieve memory graph context and produce a grounded answer.",
            prompt_id="memory_query",
            required_context_type="QueryRetrievalPlanningContext",
            produced_context_type="AnswerContext",
            allowed_tools=[
                "query_memory_context",
                "get_context_package",
                "get_entity_detail",
                "get_memories_involving_node",
                "get_timeline",
                "get_neighborhood_view",
                "get_map_view",
                "get_target_evidence",
                "get_latest_contact_details",
                "request_user_clarification",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "start_memory_ingestion",
                "update_memory_graph",
                "raw_graph_query",
            ],
            handoff_targets=[
                "query_retrieval_planning",
                "query_context_retrieval",
                "answer_generation",
            ],
            model_task="memory_query",
        ),
        AgenticStateId.GRAPH_UPDATE: AgenticStateConfig(
            state_id=AgenticStateId.GRAPH_UPDATE,
            purpose="Update the memory graph through deterministic read/write tools.",
            prompt_id="graph_update",
            required_context_type="GraphUpdateContext",
            produced_context_type="ToolResultContext",
            allowed_tools=[
                "resolve_graph_update_targets",
                "get_context_package",
                "get_entity_detail",
                "get_neighborhood_view",
                "get_target_evidence",
                "get_timeline",
                "create_memory_log",
                "create_graph_node",
                "patch_graph_node",
                "upsert_graph_relationship",
                "create_relationship_state",
                "request_user_clarification",
            ],
            forbidden_tools=[
                "apply_merge",
                "raw_graph_query",
                "delete_graph_node",
                "archive_memory",
            ],
            handoff_targets=[
                "graph_update_target_resolution",
                "graph_update_execution",
                "clarification_waiting",
            ],
            max_tool_calls=8,
            model_task="graph_update",
        ),
        AgenticStateId.CONTRADICTION_REVIEW: AgenticStateConfig(
            state_id=AgenticStateId.CONTRADICTION_REVIEW,
            purpose="Judge a grounded contradiction doubt without mutating graph state.",
            prompt_id="contradiction_review",
            required_context_type="ContradictionReviewContext",
            produced_context_type="ContradictionJudgeResultContext",
            allowed_tools=[
                "get_node_detail",
                "get_target_evidence",
                "get_neighborhood_view",
                "get_change_records",
                "get_relationship_state_history",
                "request_user_clarification",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "create_contradiction_record",
                "apply_merge",
                "raw_graph_query",
            ],
            handoff_targets=[
                "write_plan_ready",
                "clarification_waiting",
                "validation_resolution",
            ],
            model_task="contradiction_review",
        ),
    }
