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
                "cancel_pending_process",
                "get_conversation_status",
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
    }
