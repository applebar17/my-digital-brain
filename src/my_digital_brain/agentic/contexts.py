from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from my_digital_brain.agentic.base import AgenticModel, utc_now
from my_digital_brain.agentic.enums import (
    ChannelModality,
    ConfirmationRiskLevel,
    ContradictionDecision,
    ContradictionGraphAction,
    ContradictionResultIntent,
    ContradictionSeverity,
    CorrectionAction,
    MaintenanceSuggestionType,
    ProfileMemoryCategory,
    ProfileMemoryStability,
    ProfileMemoryVisibility,
    ResponseRenderStyle,
    ToolResultStatus,
)
from my_digital_brain.agentic.messages import NeutralConversationMessage
from my_digital_brain.core.ids import new_uuid


class ChannelSessionMetadata(AgenticModel):
    """Backend-owned channel/session metadata.

    This object may be passed between backend states, but it must not be passed
    directly into model-facing prompts.
    """

    channel: str
    conversation_id: str
    owner_id: str
    session_id: str | None = None
    sender_id: str | None = None
    message_id: str | None = None
    received_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelContextProjection(AgenticModel):
    """Minimal model-facing projection of channel metadata when it is useful."""

    modality: ChannelModality = ChannelModality.TEXT
    render_style: ResponseRenderStyle = ResponseRenderStyle.PLAIN_TEXT
    source_refs: list[str] = Field(default_factory=list)
    transcript_uncertainty: str | None = None
    current_time: datetime | None = None
    timezone: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PendingProcessContext(AgenticModel):
    process_id: str
    kind: str
    status: str
    question: str | None = None
    unresolved_targets: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    compact_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationContext(AgenticModel):
    context_id: str = Field(default_factory=new_uuid)
    current_message: NeutralConversationMessage
    history: list[NeutralConversationMessage] = Field(default_factory=list)
    compacted_summary: str | None = None
    current_time: datetime = Field(default_factory=utc_now)
    timezone: str = "UTC"
    pending_process: PendingProcessContext | None = None
    pending_processes: list[PendingProcessContext] = Field(default_factory=list)
    channel_metadata: ChannelSessionMetadata | None = None
    channel_projection: ChannelContextProjection | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_facing_payload(self) -> dict[str, Any]:
        """Return prompt-safe context without backend-only channel metadata."""

        return self.model_dump(
            mode="json",
            exclude={"channel_metadata"},
            exclude_none=True,
        )


class EvidenceSpan(AgenticModel):
    evidence_id: str = Field(default_factory=new_uuid)
    text: str
    span_start: int | None = Field(default=None, ge=0)
    span_end: int | None = Field(default=None, ge=0)
    source_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceContext(AgenticModel):
    source_id: str
    normalized_text: str | None = None
    transcript_text: str | None = None
    media_refs: list[str] = Field(default_factory=list)
    source_time: datetime | None = None
    received_at: datetime | None = None
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MentionContextItem(AgenticModel):
    mention_id: str = Field(default_factory=new_uuid)
    kind: str
    text: str
    evidence_text: str | None = None
    span_start: int | None = Field(default=None, ge=0)
    span_end: int | None = Field(default=None, ge=0)
    hints: dict[str, Any] = Field(default_factory=dict)


class MentionScanContext(AgenticModel):
    mention_scan_id: str = Field(default_factory=new_uuid)
    source_id: str
    mentions: list[MentionContextItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphContextPackage(AgenticModel):
    package_id: str = Field(default_factory=new_uuid)
    aliases: dict[str, str] = Field(default_factory=dict)
    candidate_matches: list[dict[str, Any]] = Field(default_factory=list)
    relationship_contexts: list[dict[str, Any]] = Field(default_factory=list)
    evidence_summaries: list[dict[str, Any]] = Field(default_factory=list)
    known_ambiguities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanningContext(AgenticModel):
    source: SourceContext
    conversation: ConversationContext
    mention_scan: MentionScanContext | None = None
    graph_context: GraphContextPackage | None = None
    pending_clarification_answer: str | None = None
    current_time: datetime = Field(default_factory=utc_now)
    timezone: str = "UTC"
    prior_tool_outputs: list["ToolResultContext"] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionTaskContext(AgenticModel):
    task_id: str
    task_type: str
    schema_id: str
    evidence: EvidenceSpan
    graph_aliases: dict[str, str] = Field(default_factory=dict)
    local_candidate_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateGraphContext(AgenticModel):
    candidate_graph_id: str = Field(default_factory=new_uuid)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    local_refs: dict[str, str] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResolutionContext(AgenticModel):
    candidate_graph: CandidateGraphContext
    graph_context: GraphContextPackage | None = None
    registries: dict[str, list[str]] = Field(default_factory=dict)
    resolver_constraints: dict[str, Any] = Field(default_factory=dict)
    pending_answer_context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolResultContext(AgenticModel):
    result_id: str = Field(default_factory=new_uuid)
    tool_name: str
    status: ToolResultStatus = ToolResultStatus.OK
    summary: str
    important_refs: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    recommended_next_action: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnswerContext(AgenticModel):
    question: str
    context_package: dict[str, Any]
    evidence_rules: list[str] = Field(default_factory=list)
    answer_style_hints: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryRetrievalPlanningContext(AgenticModel):
    question: str
    conversation: ConversationContext
    entity_hints: list[str] = Field(default_factory=list)
    time_hints: list[str] = Field(default_factory=list)
    place_hints: list[str] = Field(default_factory=list)
    seed_aliases: dict[str, str] = Field(default_factory=dict)
    desired_view: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryRetrievalPlan(AgenticModel):
    question: str
    seed_id: str | None = None
    query_text: str | None = None
    view_type: str = "context_package"
    include_history: bool = True
    timeline_limit: int = Field(default=20, ge=1, le=200)
    relationship_limit: int = Field(default=50, ge=1, le=200)
    evidence_requirements: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryRetrievalResultContext(AgenticModel):
    question: str
    plan: QueryRetrievalPlan
    seed_id: str | None = None
    seed_title: str | None = None
    context_package: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    no_memory_reason: str | None = None
    uncertainty_notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CorrectionIntakeContext(AgenticModel):
    correction_text: str
    conversation: ConversationContext
    target_hints: list[str] = Field(default_factory=list)
    graph_context: GraphContextPackage | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    current_time: datetime = Field(default_factory=utc_now)
    timezone: str = "UTC"
    metadata: dict[str, Any] = Field(default_factory=dict)


class CorrectionProposalContext(AgenticModel):
    proposal_id: str = Field(default_factory=new_uuid)
    correction_text: str
    action: CorrectionAction = CorrectionAction.NEEDS_TARGET
    target_id: str | None = None
    target_label: str | None = None
    field_path: str | None = None
    current_value: Any | None = None
    proposed_value: Any | None = None
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True
    risk_level: ConfirmationRiskLevel = ConfirmationRiskLevel.MEDIUM
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_targeted_action(self) -> "CorrectionProposalContext":
        if self.action != CorrectionAction.NEEDS_TARGET.value and not self.target_id:
            raise ValueError("Correction proposals with an action require target_id.")
        if self.action != CorrectionAction.NO_CHANGE.value and not self.reason.strip():
            raise ValueError("Correction proposals require a reason.")
        return self


class ConfirmationHandoffContext(AgenticModel):
    confirmation_id: str = Field(default_factory=new_uuid)
    proposal: CorrectionProposalContext
    question: str
    target_refs: list[str] = Field(default_factory=list)
    required_user_action: str = "confirm_or_cancel"
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContradictionReviewContext(AgenticModel):
    judge_request_id: str = Field(default_factory=new_uuid)
    proposed_write_ref: str | None = None
    proposed_write: dict[str, Any] = Field(default_factory=dict)
    graph_context: GraphContextPackage | None = None
    affected_entity_refs: list[str] = Field(default_factory=list)
    affected_relationship_refs: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    agent_doubt: str
    requested_at: datetime = Field(default_factory=utc_now)
    prior_tool_outputs: list["ToolResultContext"] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_grounded_doubt(self) -> "ContradictionReviewContext":
        if not self.agent_doubt.strip():
            raise ValueError("Contradiction review requires an agent_doubt explanation.")
        if not (self.proposed_write_ref or self.proposed_write):
            raise ValueError("Contradiction review requires proposed write context.")
        return self


class ContradictionJudgeResultContext(AgenticModel):
    judge_decision_id: str = Field(default_factory=new_uuid)
    judge_request_id: str
    intent: ContradictionResultIntent = Field(
        description=(
            "Workflow intent: needs_context, needs_clarification, "
            "emit_verdict, or fail_safe."
        ),
    )
    decision: ContradictionDecision
    severity: ContradictionSeverity = ContradictionSeverity.LOW
    reason: str
    graph_action: ContradictionGraphAction
    clarification_question: str | None = None
    affected_refs: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    inspected_context_refs: list[str] = Field(default_factory=list)
    requires_user_input: bool = False
    blocking: bool = False
    recommended_next_action: str | None = None
    resume_context: dict[str, Any] = Field(default_factory=dict)
    decided_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_intent_coherence(self) -> "ContradictionJudgeResultContext":
        needs_question = (
            self.intent == ContradictionResultIntent.NEEDS_CLARIFICATION.value
            or self.decision == ContradictionDecision.NEEDS_CLARIFICATION.value
            or self.graph_action == ContradictionGraphAction.ASK_USER.value
        )
        if self.intent == ContradictionResultIntent.EMIT_VERDICT.value and needs_question:
            raise ValueError("emit_verdict cannot ask the user for clarification.")
        if needs_question and not self.clarification_question:
            raise ValueError("Clarification decisions require clarification_question.")
        if needs_question:
            self.intent = ContradictionResultIntent.NEEDS_CLARIFICATION
            self.decision = ContradictionDecision.NEEDS_CLARIFICATION
            self.graph_action = ContradictionGraphAction.ASK_USER
            self.requires_user_input = True
            self.blocking = True
        if self.intent == ContradictionResultIntent.FAIL_SAFE.value:
            self.requires_user_input = False
        return self


class ProfileExtractionContext(AgenticModel):
    source: SourceContext
    conversation: ConversationContext | None = None
    owner_person_id: str | None = None
    current_profile_summary: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    current_time: datetime = Field(default_factory=utc_now)
    timezone: str = "UTC"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProfileMemoryCandidateContext(AgenticModel):
    candidate_id: str = Field(default_factory=new_uuid)
    profile_key: str
    category: ProfileMemoryCategory
    value: str
    description: str
    original_user_words: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    evidence_text: str | None = None
    stability: ProfileMemoryStability = ProfileMemoryStability.TEMPORARY
    visibility: ProfileMemoryVisibility = ProfileMemoryVisibility.HIDDEN
    requires_confirmation: bool = False
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProfileExtractionResultContext(AgenticModel):
    extraction_id: str = Field(default_factory=new_uuid)
    source_id: str
    candidates: list[ProfileMemoryCandidateContext] = Field(default_factory=list)
    rejected_observations: list[str] = Field(default_factory=list)
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MaintenanceReviewContext(AgenticModel):
    review_id: str = Field(default_factory=new_uuid)
    trigger: str
    graph_context: GraphContextPackage | None = None
    target_refs: list[str] = Field(default_factory=list)
    pending_processes: list[PendingProcessContext] = Field(default_factory=list)
    current_time: datetime = Field(default_factory=utc_now)
    timezone: str = "UTC"
    metadata: dict[str, Any] = Field(default_factory=dict)


class MaintenanceSuggestionContext(AgenticModel):
    suggestion_id: str = Field(default_factory=new_uuid)
    suggestion_type: MaintenanceSuggestionType
    target_refs: list[str] = Field(default_factory=list)
    reason: str
    recommended_action: str
    evidence_refs: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True
    risk_level: ConfirmationRiskLevel = ConfirmationRiskLevel.MEDIUM
    metadata: dict[str, Any] = Field(default_factory=dict)


class MaintenanceReviewResultContext(AgenticModel):
    review_id: str
    suggestions: list[MaintenanceSuggestionContext] = Field(default_factory=list)
    no_action_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_result_has_signal(self) -> "MaintenanceReviewResultContext":
        if not self.suggestions and not self.no_action_reason:
            raise ValueError("Maintenance review requires suggestions or no_action_reason.")
        return self
