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
                "propose_memory_correction",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "raw_graph_query",
                "focused_extraction",
            ],
            handoff_targets=[
                "memory_ingestion_precheck",
                "memory_query",
                "correction_intake",
            ],
            model_task="conversation_entry",
        ),
        AgenticStateId.PENDING_PROCESS_REVIEW: AgenticStateConfig(
            state_id=AgenticStateId.PENDING_PROCESS_REVIEW,
            purpose="Review a message while a pending process is active.",
            prompt_id="pending_process_review",
            required_context_type="ConversationContext",
            produced_context_type="ToolResultContext",
            allowed_tools=[
                "resume_pending_process",
                "start_memory_ingestion",
                "query_memory_context",
                "propose_memory_correction",
                "pause_pending_process",
                "cancel_pending_process",
                "request_user_clarification",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "raw_graph_query",
                "focused_extraction",
            ],
            handoff_targets=[
                "resume_pending_process",
                "memory_ingestion_precheck",
                "memory_query",
                "correction_intake",
                "pause_pending_process",
                "cancel_pending_process",
            ],
            model_task="pending_process_review",
        ),
        AgenticStateId.MEMORY_INGESTION_PLANNING: AgenticStateConfig(
            state_id=AgenticStateId.MEMORY_INGESTION_PLANNING,
            purpose="Plan memory extraction tasks from source context and compact graph context.",
            prompt_id="ingestion_planner",
            required_context_type="PlanningContext",
            produced_context_type="ExtractionPlan",
            allowed_tools=[
                "request_graph_context_expansion",
                "request_contradiction_review",
                "request_user_clarification",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "raw_graph_query",
                "apply_merge",
                "execute_memory_correction",
            ],
            handoff_targets=[
                "simple_extraction",
                "focused_extraction",
                "graph_context_retrieval",
                "clarification_waiting",
            ],
            model_task="memory_ingestion_planning",
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
                "propose_memory_correction",
                "raw_graph_query",
            ],
            handoff_targets=[
                "query_retrieval_planning",
                "query_context_retrieval",
                "answer_generation",
            ],
            model_task="memory_query",
        ),
        AgenticStateId.CORRECTION_INTAKE: AgenticStateConfig(
            state_id=AgenticStateId.CORRECTION_INTAKE,
            purpose="Turn a user correction into a safe confirmation-aware proposal.",
            prompt_id="correction_intake",
            required_context_type="CorrectionIntakeContext",
            produced_context_type="CorrectionProposalContext",
            allowed_tools=[
                "resolve_correction_target",
                "get_entity_detail",
                "get_target_evidence",
                "build_correction_proposal",
                "request_user_confirmation",
                "request_user_clarification",
            ],
            forbidden_tools=[
                "execute_graph_write_plan",
                "apply_merge",
                "raw_graph_query",
                "execute_memory_correction",
            ],
            handoff_targets=[
                "correction_target_resolution",
                "correction_proposal",
                "confirmation_waiting",
                "correction_execution",
            ],
            model_task="correction_intake",
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
