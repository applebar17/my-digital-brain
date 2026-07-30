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
    max_tool_calls: int = Field(default=50, ge=0)
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
                "query_memory",
                "ingest_memory",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "raw_graph_query",
                "focused_extraction",
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
                "ask_clarification",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "ingest_memory",
                "update_memory_graph",
                "raw_graph_query",
                "focused_extraction",
            ],
            max_tool_calls=50,
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
                "ask_clarification",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "ingest_memory",
                "update_memory_graph",
                "raw_graph_query",
                "focused_extraction",
            ],
            max_tool_calls=50,
            model_task="planning_checkpoint",
        ),
        AgenticStateId.MEMORY_LOG_EXTRACTION: AgenticStateConfig(
            state_id=AgenticStateId.MEMORY_LOG_EXTRACTION,
            purpose=(
                "Extract one backend-facing MemoryLog draft from a planned "
                "memory-log target without mutating storage."
            ),
            prompt_id="memory_log_extraction",
            required_context_type="PlanningTransformContext",
            produced_context_type="MemoryLogDraftBatch",
            allowed_tools=[
                "get_context_package",
                "get_entity_detail",
                "get_neighborhood_view",
                "get_target_evidence",
                "ask_clarification",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "ingest_memory",
                "update_memory_graph",
                "raw_graph_query",
                "focused_extraction",
            ],
            max_tool_calls=50,
            model_task="memory_log_extraction",
        ),
        AgenticStateId.MEMORY_QUERY: AgenticStateConfig(
            state_id=AgenticStateId.MEMORY_QUERY,
            purpose="Retrieve memory graph context and produce a grounded answer.",
            prompt_id="memory_query",
            required_context_type="QueryRetrievalPlanningContext",
            produced_context_type="AnswerContext",
            allowed_tools=[
                "get_context_package",
                "get_entity_detail",
                "get_memories_involving_node",
                "get_timeline",
                "get_neighborhood_view",
                "get_map_view",
                "get_target_evidence",
                "get_latest_contact_details",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "ingest_memory",
                "update_memory_graph",
                "ask_clarification",
                "raw_graph_query",
            ],
            model_task="memory_query",
        ),
        AgenticStateId.MEMORY_INGESTION: AgenticStateConfig(
            state_id=AgenticStateId.MEMORY_INGESTION,
            purpose="Plan memory ingestion actions from history and hydrated context.",
            prompt_id="memory_ingestion",
            required_context_type="MemoryIngestionContext",
            produced_context_type="MemoryIngestionResultContext",
            allowed_tools=[
                "get_context_package",
                "get_entity_detail",
                "get_neighborhood_view",
                "get_target_evidence",
                "run_memory_creation",
                "update_memory_graph",
                "ask_clarification",
            ],
            forbidden_tools=[
                "ingest_memory",
                "query_memory",
                "execute_graph_write_plan",
                "raw_graph_query",
            ],
            max_tool_calls=50,
            model_task="memory_ingestion",
        ),
        AgenticStateId.MEMORY_CREATION: AgenticStateConfig(
            state_id=AgenticStateId.MEMORY_CREATION,
            purpose="Execute one creation-oriented memory plan action through deterministic tools.",
            prompt_id="memory_creation",
            required_context_type="MemoryCreationContext",
            produced_context_type="MemoryCreationResultContext",
            allowed_tools=[
                "get_context_package",
                "get_entity_detail",
                "get_neighborhood_view",
                "get_target_evidence",
                "create_memory_log",
                "create_graph_node",
                "upsert_graph_relationship",
                "create_relationship_state",
                "update_memory_graph",
                "ask_clarification",
            ],
            forbidden_tools=[
                "ingest_memory",
                "query_memory",
                "execute_graph_write_plan",
                "raw_graph_query",
            ],
            max_tool_calls=50,
            model_task="memory_creation",
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
                "ask_clarification",
            ],
            forbidden_tools=[
                "apply_merge",
                "raw_graph_query",
                "delete_graph_node",
                "archive_memory",
            ],
            max_tool_calls=50,
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
                "ask_clarification",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "create_contradiction_record",
                "apply_merge",
                "raw_graph_query",
            ],
            model_task="contradiction_review",
        ),
        AgenticStateId.PROFILE_DUPLICATION: AgenticStateConfig(
            state_id=AgenticStateId.PROFILE_DUPLICATION,
            purpose="Evaluate or reproduce the owner's approved profile without graph writes.",
            prompt_id="profile_duplication",
            required_context_type="PlanningTransformContext",
            produced_context_type="PlanningTransformResultContext",
            allowed_tools=[],
            forbidden_tools=[
                "execute_graph_write_plan",
                "ingest_memory",
                "update_memory_graph",
                "create_graph_node",
                "patch_graph_node",
                "upsert_graph_relationship",
                "raw_graph_query",
            ],
            max_tool_calls=50,
            model_task="profile_duplication",
        ),
        AgenticStateId.CLARIFICATION_AGENT: AgenticStateConfig(
            state_id=AgenticStateId.CLARIFICATION_AGENT,
            purpose="Resolve caller-supplied doubts through read-only context and user interaction.",
            prompt_id="clarification_agent",
            required_context_type="ClarificationSessionInput",
            produced_context_type="ClarificationResolutionReport",
            allowed_tools=[
                "get_context_package",
                "get_entity_detail",
                "get_neighborhood_view",
                "get_target_evidence",
            ],
            forbidden_tools=[
                "ask_clarification",
                "execute_graph_write_plan",
                "create_graph_node",
                "patch_graph_node",
                "create_memory_log",
                "upsert_graph_relationship",
                "raw_graph_query",
            ],
            max_tool_calls=50,
            model_task="clarification_agent",
        ),
    }
