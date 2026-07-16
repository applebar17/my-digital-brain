from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Literal

from pydantic import Field, model_validator

from my_digital_brain.agentic.base import AgenticModel, utc_now
from my_digital_brain.agentic.enums import (
    ChannelModality,
    ConfirmationRiskLevel,
    ContradictionDecision,
    ContradictionGraphAction,
    ContradictionResultIntent,
    ContradictionSeverity,
    MaintenanceSuggestionType,
    MemoryPlanActionType,
    MemoryPlanningPhase,
    PlanExecutionMode,
    ProfileMemoryCategory,
    ProfileMemoryStability,
    ProfileMemoryVisibility,
    ReasoningInsightKind,
    ReasoningStorageRecommendationType,
    ResponseRenderStyle,
    ToolResultStatus,
)
from my_digital_brain.agentic.messages import NeutralConversationMessage
from my_digital_brain.agentic.refs import RefContext
from my_digital_brain.core.ids import new_uuid
from my_digital_brain.core.owner_context import OwnerSnapshot

_PROPOSED_REF_RE = re.compile(r"\b(?:node|memory|edge|context|media)_new_[a-z0-9_]{1,64}\b")
_VISIBLE_REF_RE = re.compile(r"^(?:(?:node|memory|edge|context|media)_[0-9]{4}|(?:node|memory|edge|context|media)_new_[a-z0-9_]{1,64})$")

BACKEND_ONLY_KEYS = {
    "metadata",
    "checkpoint_id",
    "context_id",
    "package_id",
    "process_id",
    "candidate_id",
    "extraction_id",
    "review_id",
    "suggestion_id",
}


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


class ConversationContext(AgenticModel):
    context_id: str = Field(default_factory=new_uuid)
    current_message: NeutralConversationMessage
    history: list[NeutralConversationMessage] = Field(default_factory=list)
    compacted_summary: str | None = None
    current_time: datetime = Field(default_factory=utc_now)
    timezone: str = "UTC"
    channel_metadata: ChannelSessionMetadata | None = None
    channel_projection: ChannelContextProjection | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_facing_payload(self) -> dict[str, Any]:
        """Return prompt-safe context without backend-only channel metadata."""

        payload = self.model_dump(
            mode="json",
            exclude={"channel_metadata"},
            exclude_none=True,
        )
        return payload


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


class GraphContextPackage(AgenticModel):
    package_id: str = Field(default_factory=new_uuid)
    aliases: dict[str, str] = Field(default_factory=dict)
    candidate_matches: list[dict[str, Any]] = Field(default_factory=list)
    relationship_contexts: list[dict[str, Any]] = Field(default_factory=list)
    evidence_summaries: list[dict[str, Any]] = Field(default_factory=list)
    known_ambiguities: list[str] = Field(default_factory=list)
    owner_snapshot: OwnerSnapshot | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReasoningPurposeGuidelines(AgenticModel):
    purpose_id: str = "general"
    goal: str
    focus_areas: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)
    output_usage: str | None = None
    forbidden_assumptions: list[str] = Field(default_factory=list)


class ReasoningCheckpointContext(AgenticModel):
    checkpoint_id: str = Field(default_factory=new_uuid)
    purpose: ReasoningPurposeGuidelines
    input_context: dict[str, Any] = Field(default_factory=dict)
    conversation: ConversationContext | None = None
    graph_context: GraphContextPackage | None = None
    owner_snapshot: OwnerSnapshot | None = None
    current_time: datetime = Field(default_factory=utc_now)
    timezone: str = "UTC"
    prior_tool_outputs: list["ToolResultContext"] = Field(default_factory=list)
    expected_output_schema: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_facing_payload(self) -> dict[str, Any]:
        return _compact_prompt_payload(
            {
                "purpose": self.purpose,
                "input_context": self.input_context,
                "conversation": self.conversation,
                "graph_context": self.graph_context,
                "owner_snapshot": self.owner_snapshot,
                "current_time": self.current_time,
                "timezone": self.timezone,
                "prior_tool_outputs": self.prior_tool_outputs,
                "expected_output_schema": self.expected_output_schema,
            },
        )

    def system_prompt_payload(self) -> dict[str, Any]:
        return _compact_prompt_payload(
            {
                "purpose": _reasoning_prompt_purpose(
                    self.purpose,
                    self.input_context,
                ),
                "task_context": _reasoning_prompt_task_context(
                    self.input_context,
                    graph_context=self.graph_context,
                    current_time=self.current_time,
                    timezone=self.timezone,
                ),
            },
        )


class ReasoningInsightContext(AgenticModel):
    insight_type: ReasoningInsightKind
    summary: str
    evidence_text: str | None = None
    affected_refs: list[str] = Field(default_factory=list)
    recommended_next_action: str | None = None
    caution: str | None = None


class ReasoningClarificationCandidateContext(AgenticModel):
    question: str
    reason: str
    target_refs: list[str] = Field(default_factory=list)
    suggested_answers: list[str] = Field(default_factory=list)
    blocking: bool = True


class ReasoningEntityUnderstandingContext(AgenticModel):
    mention_text: str
    interpretation: str
    existing_alias_refs: list[str] = Field(default_factory=list)
    should_be_node: bool = False
    possible_node_type: str | None = None
    metadata_candidate_keys: list[str] = Field(default_factory=list)
    ambiguity_notes: list[str] = Field(default_factory=list)


class ReasoningStorageRecommendationContext(AgenticModel):
    subject: str
    recommendation_type: ReasoningStorageRecommendationType
    reason: str
    target_refs: list[str] = Field(default_factory=list)
    suggested_property_keys: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


class ReasoningCheckpointResultContext(AgenticModel):
    checkpoint_id: str
    purpose_id: str
    summary: str
    insights: list[ReasoningInsightContext] = Field(default_factory=list)
    clarification_candidates: list[ReasoningClarificationCandidateContext] = Field(
        default_factory=list,
    )
    entity_understandings: list[ReasoningEntityUnderstandingContext] = Field(
        default_factory=list,
    )
    storage_recommendations: list[ReasoningStorageRecommendationContext] = Field(
        default_factory=list,
    )
    context_gaps: list[str] = Field(default_factory=list)
    recommended_next_action: str | None = None

    @model_validator(mode="after")
    def _validate_signal(self) -> "ReasoningCheckpointResultContext":
        if not self.summary.strip():
            raise ValueError("Reasoning checkpoint requires a summary.")
        if not (
            self.insights
            or self.clarification_candidates
            or self.entity_understandings
            or self.storage_recommendations
            or self.context_gaps
        ):
            raise ValueError("Reasoning checkpoint requires at least one useful output asset.")
        return self


class PlanningContext(AgenticModel):
    source: SourceContext
    conversation: ConversationContext
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
    owner_snapshot: OwnerSnapshot | None = None
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


class NodeReasoningHighlights(AgenticModel):
    persons: str = ""
    places: str = ""
    events: str = ""
    social_circles: str = ""
    topics_or_objects: str = ""
    other: str = ""

    def has_signal(self) -> bool:
        return any(
            value.strip()
            for value in (
                self.persons,
                self.places,
                self.events,
                self.social_circles,
                self.topics_or_objects,
                self.other,
            )
        )


class EdgeReasoningHighlights(AgenticModel):
    family: str = ""
    relationships: str = ""
    perception_or_affect: str = ""
    event_place_links: str = ""
    other: str = ""

    def has_signal(self) -> bool:
        return any(
            value.strip()
            for value in (
                self.family,
                self.relationships,
                self.perception_or_affect,
                self.event_place_links,
                self.other,
            )
        )


class ReasoningHighlights(AgenticModel):
    nodes: NodeReasoningHighlights = Field(default_factory=NodeReasoningHighlights)
    logs: list[str] = Field(default_factory=list)
    edges: EdgeReasoningHighlights = Field(default_factory=EdgeReasoningHighlights)

    def has_signal(self) -> bool:
        return self.nodes.has_signal() or bool(self.logs) or self.edges.has_signal()


class AliasReasoningHint(AgenticModel):
    main_mention: str = Field(description="Primary source mention or normalized name.")
    aliases: list[str] = Field(
        default_factory=list,
        description="Possible aliases, nicknames, misspellings, or role mentions.",
    )
    notes: str | None = None

    @model_validator(mode="after")
    def _validate_signal(self) -> "AliasReasoningHint":
        if not self.main_mention.strip():
            raise ValueError("Alias hint requires a main_mention.")
        self.aliases = [alias for alias in self.aliases if alias.strip()]
        return self


class IrrelevantDetailHint(AgenticModel):
    detail: str = Field(description="Detail that later states should usually ignore.")
    reason: str | None = None
    category: str | None = None

    @model_validator(mode="after")
    def _validate_signal(self) -> "IrrelevantDetailHint":
        if not self.detail.strip():
            raise ValueError("Irrelevant detail requires detail text.")
        return self


class ReasoningAmbiguity(AgenticModel):
    subject: str = Field(description="Ambiguous mention, relation, or memory boundary.")
    description: str = Field(description="Why the subject is ambiguous.")
    possible_interpretations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_signal(self) -> "ReasoningAmbiguity":
        if not self.subject.strip() or not self.description.strip():
            raise ValueError("Ambiguity requires subject and description.")
        return self


class ReasoningDuplicateNote(AgenticModel):
    mention: str = Field(description="Source mention or candidate identity needing duplicate checks.")
    note: str = Field(description="Duplicate or resolution guidance for the planner.")
    candidate_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_signal(self) -> "ReasoningDuplicateNote":
        if not self.mention.strip() or not self.note.strip():
            raise ValueError("Duplicate note requires mention and note.")
        return self


class MemoryIngestionReasoning(AgenticModel):
    highlights: ReasoningHighlights = Field(default_factory=ReasoningHighlights)
    possible_aliases: list[AliasReasoningHint] = Field(default_factory=list)
    irrelevant_details: list[IrrelevantDetailHint] = Field(default_factory=list)
    ambiguities: list[ReasoningAmbiguity] = Field(default_factory=list)
    duplicate_or_resolution_notes: list[ReasoningDuplicateNote] = Field(default_factory=list)
    missing_context_questions: list[str] = Field(default_factory=list)
    planning_guidance: str = ""

    @model_validator(mode="after")
    def _validate_reasoning_boundary(self) -> "MemoryIngestionReasoning":
        _reject_proposed_refs(self.model_dump(mode="json"))
        useful = (
            self.highlights.has_signal()
            or self.possible_aliases
            or self.irrelevant_details
            or self.ambiguities
            or self.duplicate_or_resolution_notes
            or any(question.strip() for question in self.missing_context_questions)
            or self.planning_guidance.strip()
        )
        if not useful:
            raise ValueError("MemoryIngestionReasoning requires at least one useful signal.")
        self.missing_context_questions = [
            question for question in self.missing_context_questions if question.strip()
        ]
        return self


class AgenticToolPayload(AgenticModel):
    summary: str
    created_refs: list[str] = Field(default_factory=list)
    updated_refs: list[str] = Field(default_factory=list)
    affected_graph_ids: list[str] = Field(default_factory=list)
    refreshed_vector_scopes: list[str] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    suggested_next_action: str | None = None
    error_code: str | None = None
    retryable: bool | None = None
    validation_details: dict[str, Any] | None = None
    ref_context_delta: dict[str, Any] | None = None
    ref_packets: list[dict[str, Any]] = Field(default_factory=list)
    resolved_clarifications: list[dict[str, Any]] = Field(default_factory=list)


class PlannedRefPacket(AgenticModel):
    ref: str
    object_kind: str
    label: str | None = None
    type: str | None = None
    name: str | None = None
    summary: str | None = None
    aliases: list[str] = Field(default_factory=list)
    source_mentions: list[str] = Field(default_factory=list)
    status: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _validate_ref(self) -> "PlannedRefPacket":
        if not _VISIBLE_REF_RE.match(self.ref):
            raise ValueError(
                "PlannedRefPacket.ref must be a local ref like node_0001, "
                "node_new_lorenzo, memory_new_beach_outing, or context_new_perception."
            )
        _validate_ref_kind_prefix(self.ref, self.object_kind)
        return self


class NodePlanPacket(AgenticModel):
    planned_refs: list[PlannedRefPacket] = Field(default_factory=list)
    resolved_refs: list[PlannedRefPacket] = Field(default_factory=list)
    duplicate_notes: list[str] = Field(default_factory=list)
    ignored_mentions: list[str] = Field(default_factory=list)
    summary: str = ""

    @model_validator(mode="after")
    def _validate_signal(self) -> "NodePlanPacket":
        _validate_unique_refs(
            [item.ref for item in [*self.planned_refs, *self.resolved_refs]],
            "NodePlanPacket",
        )
        if not (
            self.planned_refs
            or self.resolved_refs
            or self.duplicate_notes
            or self.ignored_mentions
            or self.summary.strip()
        ):
            raise ValueError("NodePlanPacket requires at least one useful signal.")
        return self


class MemoryPlanPacket(AgenticModel):
    planned_refs: list[PlannedRefPacket] = Field(default_factory=list)
    host_refs: list[str] = Field(default_factory=list)
    involved_refs: list[str] = Field(default_factory=list)
    context_refs: list[str] = Field(default_factory=list)
    weak_edge_notes: list[str] = Field(default_factory=list)
    summary: str = ""

    @model_validator(mode="after")
    def _validate_refs_and_signal(self) -> "MemoryPlanPacket":
        packet_refs = [
            *[item.ref for item in self.planned_refs],
            *self.host_refs,
            *self.involved_refs,
            *self.context_refs,
        ]
        for ref in packet_refs:
            if not _VISIBLE_REF_RE.match(ref):
                raise ValueError(f"MemoryPlanPacket contains an invalid local ref: {ref}")
        _validate_unique_refs([item.ref for item in self.planned_refs], "MemoryPlanPacket")
        if not (
            self.planned_refs
            or self.host_refs
            or self.involved_refs
            or self.context_refs
            or self.weak_edge_notes
            or self.summary.strip()
        ):
            raise ValueError("MemoryPlanPacket requires at least one useful signal.")
        return self


class MemoryPlanStep(AgenticModel):
    step_id: str
    phase: MemoryPlanningPhase
    execution_mode: PlanExecutionMode = PlanExecutionMode.SEQUENTIAL
    actions: list["MemoryPlanAction"] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_actions(self) -> "MemoryPlanStep":
        if not self.actions:
            raise ValueError("MemoryPlanStep requires at least one action.")
        phase = MemoryPlanningPhase(self.phase)
        action_ids = [action.action_id for action in self.actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("MemoryPlanStep action_id values must be unique.")
        for action in self.actions:
            action_phase = action.metadata.get("phase") or phase.value
            action.metadata["phase"] = action_phase
        return self


class MemoryPlanAction(AgenticModel):
    action_id: str = Field(default_factory=new_uuid)
    action_type: MemoryPlanActionType
    target_refs: list[str] = Field(default_factory=list)
    rationale: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryPlan(AgenticModel):
    plan_id: str = Field(default_factory=new_uuid)
    context_refs: list[str] = Field(default_factory=list)
    actions: list[MemoryPlanAction] = Field(default_factory=list)
    steps: list[MemoryPlanStep] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_actions(self) -> "MemoryPlan":
        if not (self.actions or self.steps):
            raise ValueError("MemoryPlan requires at least one action or step.")
        return self




class NodeMemoryPlan(AgenticModel):
    summary: str
    steps: list[MemoryPlanStep] = Field(default_factory=list)
    node_plan_packet: NodePlanPacket
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_phase(self) -> "NodeMemoryPlan":
        _validate_steps_for_phase(self.steps, MemoryPlanningPhase.NODES)
        return self


class MemoryLogMemoryPlan(AgenticModel):
    summary: str
    steps: list[MemoryPlanStep] = Field(default_factory=list)
    memory_plan_packet: MemoryPlanPacket
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_phase(self) -> "MemoryLogMemoryPlan":
        _validate_steps_for_phase(self.steps, MemoryPlanningPhase.MEMORY_LOGS)
        return self


class EdgeMemoryPlan(AgenticModel):
    summary: str
    steps: list[MemoryPlanStep] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_phase_and_refs(self) -> "EdgeMemoryPlan":
        _validate_steps_for_phase(self.steps, MemoryPlanningPhase.EDGES)
        for step in self.steps:
            for action in step.actions:
                if action.action_type in {
                    MemoryPlanActionType.CREATE_RELATIONSHIP,
                    MemoryPlanActionType.CREATE_RELATIONSHIP_STATE,
                }:
                    for field_name in ("from_ref", "to_ref", "source_ref", "target_ref"):
                        value = action.payload.get(field_name)
                        if value is not None and not _VISIBLE_REF_RE.match(str(value)):
                            raise ValueError(
                                f"Edge action {action.action_id} field {field_name} must use a local ref."
                            )
        return self


class MemoryIngestionContext(AgenticModel):
    conversation: ConversationContext
    graph_context: GraphContextPackage | None = None
    current_time: datetime = Field(default_factory=utc_now)
    timezone: str = "UTC"
    prior_tool_outputs: list[ToolResultContext] = Field(default_factory=list)
    reasoning: MemoryIngestionReasoning | None = None
    reasoning_packets: list[dict[str, Any]] = Field(default_factory=list)
    node_plan: NodeMemoryPlan | None = None
    memory_plan: MemoryLogMemoryPlan | None = None
    edge_plan: EdgeMemoryPlan | None = None
    node_plan_packet: NodePlanPacket | None = None
    memory_plan_packet: MemoryPlanPacket | None = None
    ref_context: RefContext | None = None
    ref_packets: list[dict[str, Any]] = Field(default_factory=list)
    resolved_clarifications: list[dict[str, Any]] = Field(default_factory=list)
    owner_snapshot: OwnerSnapshot | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_facing_payload(self) -> dict[str, Any]:
        return _compact_prompt_payload(
            {
                "conversation": self.conversation,
                "graph_context": self.graph_context,
                "current_time": self.current_time,
                "timezone": self.timezone,
                "prior_tool_outputs": self.prior_tool_outputs,
                "reasoning": self.reasoning,
                "reasoning_packets": self.reasoning_packets,
                "node_plan": self.node_plan,
                "memory_plan": self.memory_plan,
                "edge_plan": self.edge_plan,
                "node_plan_packet": self.node_plan_packet,
                "memory_plan_packet": self.memory_plan_packet,
                "ref_context": (
                    self.ref_context.model_facing_packet()
                    if self.ref_context is not None
                    else None
                ),
                "ref_packets": self.ref_packets,
                "resolved_clarifications": self.resolved_clarifications,
                "owner_snapshot": self.owner_snapshot,
            },
        )


class MemoryIngestionResultContext(AgenticModel):
    plan: MemoryPlan | None = None
    summary: str
    phase_summaries: list[str] = Field(default_factory=list)
    created_refs: list[str] = Field(default_factory=list)
    updated_refs: list[str] = Field(default_factory=list)
    affected_graph_ids: list[str] = Field(default_factory=list)
    ref_context_delta: dict[str, Any] | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryCreationContext(AgenticModel):
    conversation: ConversationContext
    action: MemoryPlanAction
    graph_context: GraphContextPackage | None = None
    current_time: datetime = Field(default_factory=utc_now)
    timezone: str = "UTC"
    prior_tool_outputs: list[ToolResultContext] = Field(default_factory=list)
    ref_context: RefContext | None = None
    ref_packets: list[dict[str, Any]] = Field(default_factory=list)
    resolved_clarifications: list[dict[str, Any]] = Field(default_factory=list)
    owner_snapshot: OwnerSnapshot | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_facing_payload(self) -> dict[str, Any]:
        return _compact_prompt_payload(
            {
                "conversation": self.conversation,
                "action": self.action,
                "graph_context": self.graph_context,
                "current_time": self.current_time,
                "timezone": self.timezone,
                "prior_tool_outputs": self.prior_tool_outputs,
                "ref_context": (
                    self.ref_context.model_facing_packet()
                    if self.ref_context is not None
                    else None
                ),
                "ref_packets": self.ref_packets,
                "resolved_clarifications": self.resolved_clarifications,
                "owner_snapshot": self.owner_snapshot,
            },
        )


class MemoryCreationResultContext(AgenticModel):
    action_id: str
    status: ToolResultStatus = ToolResultStatus.OK
    tool_payload: AgenticToolPayload
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphUpdateContext(AgenticModel):
    source_text: str
    conversation: ConversationContext
    guidelines: str = Field(
        default="Update the memory graph using deterministic tools.",
    )
    desired_work: str | None = None
    target_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    graph_context: GraphContextPackage | None = None
    owner_snapshot: OwnerSnapshot | None = None
    current_time: datetime = Field(default_factory=utc_now)
    timezone: str = "UTC"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContradictionReviewContext(AgenticModel):
    judge_request_id: str = Field(default_factory=new_uuid)
    proposed_write_ref: str | None = None
    proposed_write: dict[str, Any] = Field(default_factory=dict)
    graph_context: GraphContextPackage | None = None
    owner_snapshot: OwnerSnapshot | None = None
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
    owner_snapshot: OwnerSnapshot | None = None
    current_profile_summary: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    current_time: datetime = Field(default_factory=utc_now)
    timezone: str = "UTC"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProfileMemoryCandidateContext(AgenticModel):
    candidate_id: str = Field(default_factory=new_uuid)
    owner_ref: Literal["OWNER"] = "OWNER"
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
    assertion_mode: Literal["explicit", "inferred"] = "explicit"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_owner_profile_provenance(self) -> "ProfileMemoryCandidateContext":
        if not self.original_user_words or not self.original_user_words.strip():
            raise ValueError("Owner profile proposals require original_user_words.")
        if not self.source_refs:
            raise ValueError("Owner profile proposals require source_refs.")
        if self.assertion_mode == "inferred":
            self.requires_confirmation = True
            if self.stability == ProfileMemoryStability.USER_CONFIRMED:
                raise ValueError("Inferred owner traits cannot be user-confirmed.")
        if self.stability == ProfileMemoryStability.TEMPORARY:
            raise ValueError("Temporary observations do not belong in stable profile memory.")
        return self


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




def _validate_ref_kind_prefix(ref: str, object_kind: str) -> None:
    normalized = str(object_kind or "").strip().lower()
    aliases = {"memorylog": "memory", "memory_log": "memory", "relationship": "edge"}
    kind = aliases.get(normalized, normalized)
    if kind in {"node", "memory", "edge", "context", "media"} and not ref.startswith(f"{kind}_"):
        raise ValueError(f"Ref {ref} does not match object kind {object_kind}.")


def _validate_unique_refs(refs: list[str], owner: str) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for ref in refs:
        if ref in seen and ref not in duplicates:
            duplicates.append(ref)
        seen.add(ref)
    if duplicates:
        raise ValueError(f"{owner} refs must be unique: {', '.join(duplicates)}")


def _validate_steps_for_phase(
    steps: list[MemoryPlanStep],
    phase: MemoryPlanningPhase,
) -> None:
    if not steps:
        raise ValueError(f"{phase.value} plan requires at least one step.")
    for step in steps:
        if MemoryPlanningPhase(step.phase) != phase:
            raise ValueError(
                f"Plan step {step.step_id} has phase {step.phase}; expected {phase.value}."
            )


def _reject_proposed_refs(value: Any) -> None:
    if isinstance(value, str):
        match = _PROPOSED_REF_RE.search(value)
        if match:
            raise ValueError(
                "Memory ingestion reasoning must not allocate proposed refs; "
                f"found {match.group(0)}."
            )
        return
    if isinstance(value, dict):
        for item in value.values():
            _reject_proposed_refs(item)
        return
    if isinstance(value, list):
        for item in value:
            _reject_proposed_refs(item)


def _compact_prompt_payload(value: Any) -> Any:
    if hasattr(value, "model_facing_payload"):
        return _compact_prompt_payload(value.model_facing_payload())
    if hasattr(value, "model_dump"):
        return _compact_prompt_payload(value.model_dump(mode="json", exclude_none=True))
    if isinstance(value, dict):
        compacted = {
            key: _compact_prompt_payload(item)
            for key, item in value.items()
            if key not in BACKEND_ONLY_KEYS
        }
        return {
            key: item
            for key, item in compacted.items()
            if item not in (None, "", [], {})
        }
    if isinstance(value, list):
        return [
            item
            for item in (_compact_prompt_payload(item) for item in value)
            if item not in (None, "", [], {})
        ]
    return value


def _reasoning_prompt_purpose(
    purpose: ReasoningPurposeGuidelines,
    input_context: dict[str, Any],
) -> dict[str, Any]:
    instructions = list(purpose.instructions)
    rules = input_context.get("rules")
    if isinstance(rules, list):
        instructions.extend(str(rule) for rule in rules if rule)
    return {
        key: value
        for key, value in {
            "goal": purpose.goal,
            "focus_areas": list(purpose.focus_areas),
            "instructions": list(dict.fromkeys(instructions)),
        }.items()
        if value not in (None, "", [], {})
    }


def _reasoning_prompt_task_context(
    input_context: dict[str, Any],
    *,
    graph_context: GraphContextPackage | None,
    current_time: datetime,
    timezone: str,
) -> dict[str, Any]:
    return _compact_prompt_payload(
        {
            "planning_scope": input_context.get("planning_scope"),
            "graph_context_view": input_context.get("graph_context_view"),
            "graph_context": graph_context,
            "entity_packet": input_context.get("entity_packet"),
            "memory_log_packet": input_context.get("memory_log_packet"),
            "current_action": input_context.get("current_action"),
            "current_target": input_context.get("current_target"),
            "time": {
                "current_time": current_time,
                "timezone": timezone,
            },
        },
    )
