from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.ingestion.enums import (
    ClarificationStatus,
    ExtractionExecutionMode,
    ExtractionTaskType,
    GraphWritePlanStatus,
    IngestionStatus,
    MentionKind,
    ResolutionDecisionType,
    SourceChannel,
    SourceType,
)


class IngestionModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        use_enum_values=True,
    )


class EvidenceRef(IngestionModel):
    source_id: str = Field(description="Source record that contains the supporting evidence.")
    extraction_run_id: str | None = Field(
        default=None,
        description="Extraction run that produced this evidence reference, when available.",
    )
    evidence_text: str | None = Field(
        default=None,
        description="Short verbatim or near-verbatim evidence snippet from the source.",
    )
    span_start: int | None = Field(
        default=None,
        ge=0,
        description="Character start offset in the source text, when known.",
    )
    span_end: int | None = Field(
        default=None,
        ge=0,
        description="Character end offset in the source text, when known.",
    )

    @model_validator(mode="after")
    def validate_span_order(self) -> EvidenceRef:
        if self.span_start is not None and self.span_end is not None:
            if self.span_end < self.span_start:
                raise ValueError("span_end must be greater than or equal to span_start")
        return self


class TemporalScope(IngestionModel):
    valid_from: str | None = Field(
        default=None,
        description="Original or normalized lower bound for when the fact is valid.",
    )
    valid_to: str | None = Field(
        default=None,
        description="Original or normalized upper bound for when the fact is valid.",
    )
    resolved_start: str | None = Field(
        default=None,
        description="Deterministically queryable start time when a fuzzy date was resolved.",
    )
    resolved_end: str | None = Field(
        default=None,
        description="Deterministically queryable end time when a fuzzy date was resolved.",
    )
    time_precision: str | None = Field(
        default=None,
        description="Precision of the resolved time, such as day, month, year, or fuzzy.",
    )
    time_basis: str | None = Field(
        default=None,
        description="Reasoning basis for the time value, such as user stated or inferred.",
    )
    timezone: str | None = Field(
        default=None,
        description="Timezone used for resolved temporal values, when known.",
    )
    original_time_text: str | None = Field(
        default=None,
        description="Exact source wording for fuzzy or user-provided time references.",
    )


class AffectiveFields(IngestionModel):
    description: str | None = Field(
        default=None,
        description="Human-readable memory description, preserving emotional meaning.",
    )
    emotional_summary: str | None = Field(
        default=None,
        description="Concise summary of the emotional or perceptual weight of the memory.",
    )
    emotional_valence: str | None = Field(
        default=None,
        description="Qualitative emotional polarity, such as positive, negative, or mixed.",
    )
    emotional_intensity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional emotional intensity from 0 to 1 when explicitly inferable.",
    )
    emotion_tags: list[str] = Field(
        default_factory=list,
        description="Short emotion or perception tags that are useful for retrieval.",
    )
    original_user_words: str | None = Field(
        default=None,
        description="User wording worth preserving because it carries memory tone.",
    )


class SourceRecordRef(IngestionModel):
    source_id: str = Field(description="Stable identifier for the source record.")
    source_type: SourceType = Field(description="Type of source being ingested.")
    channel: SourceChannel = Field(description="Transport or origin channel for the source.")
    external_id: str | None = Field(
        default=None,
        description="Provider-specific source identifier, such as a Telegram message id.",
    )
    content_ref: str | None = Field(
        default=None,
        description="Pointer to stored raw media or source content, when available.",
    )
    raw_text: str | None = Field(
        default=None,
        description="Text content to ingest, including transcribed audio when applicable.",
    )
    derived_from_source_id: str | None = Field(
        default=None,
        description="Parent source id when this source derives from media or another source.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Governed source metadata; avoid using this for frequently queried facts.",
    )


class ExtractionRunRef(IngestionModel):
    extraction_run_id: str = Field(description="Stable identifier for the extraction run.")
    source_id: str = Field(description="Source record processed by this extraction run.")
    processor: str = Field(description="Backend processor or service that ran extraction.")
    processor_version: str | None = Field(
        default=None,
        description="Version of the processor implementation.",
    )
    model: str | None = Field(default=None, description="AI model used, when applicable.")
    prompt_version: str | None = Field(
        default=None,
        description="Prompt version used, when applicable.",
    )
    schema_version: str | None = Field(
        default=None,
        description="Structured output schema version used, when applicable.",
    )
    status: str = Field(default="created", description="Operational status of the run.")
    metadata: dict[str, Any] = Field(default_factory=dict)


class Mention(IngestionModel):
    mention_id: str = Field(default_factory=new_uuid)
    kind: MentionKind = Field(description="Semantic kind of mention found in source text.")
    text: str = Field(description="Mention text exactly as found or minimally normalized.")
    evidence_text: str | None = Field(
        default=None,
        description="Short source snippet that justifies this mention.",
    )
    span_start: int | None = Field(default=None, ge=0)
    span_end: int | None = Field(default=None, ge=0)
    possible_normalized_value: str | None = Field(
        default=None,
        description="Possible normalized value, without forcing resolution.",
    )
    ambiguity_hint: str | None = Field(
        default=None,
        description="Short note explaining ambiguity that later steps should consider.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class MentionScan(IngestionModel):
    mention_scan_id: str = Field(default_factory=new_uuid)
    source_id: str = Field(description="Source record that was scanned.")
    mentions: list[Mention] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClarificationRequest(IngestionModel):
    clarification_id: str = Field(default_factory=new_uuid)
    question: str = Field(description="Single user-facing question needed to proceed.")
    reason: str = Field(description="Why this clarification is needed.")
    target_refs: list[str] = Field(
        default_factory=list,
        description="Candidate refs, graph aliases, or source refs affected by the question.",
    )
    options: list[str] = Field(
        default_factory=list,
        description="Optional suggested answers. Free text remains allowed by default.",
    )
    free_text_allowed: bool = Field(default=True)
    blocking: bool = Field(
        default=True,
        description="Whether ingestion should wait before producing graph write candidates.",
    )
    status: ClarificationStatus = Field(default=ClarificationStatus.PROPOSED)
    created_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionTask(IngestionModel):
    task_id: str = Field(default_factory=new_uuid)
    task_type: ExtractionTaskType = Field(
        description="Focused extraction task assigned by the planner.",
    )
    target_ref: str | None = Field(
        default=None,
        description="Candidate ref, graph alias, or source ref this task focuses on.",
    )
    evidence_text: str | None = Field(
        default=None,
        description="Minimal text span the task should use as primary evidence.",
    )
    source_refs: list[str] = Field(
        default_factory=list,
        description="Source ids that the extractor may use.",
    )
    expected_output: str | None = Field(
        default=None,
        description="Short instruction describing the structured object expected.",
    )
    required_context_refs: list[str] = Field(
        default_factory=list,
        description="Graph aliases or candidate refs that must be included in context.",
    )
    notes: str | None = Field(
        default=None,
        description="Planner notes for focused extraction. Keep short and operational.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionPlan(IngestionModel):
    extraction_plan_id: str = Field(default_factory=new_uuid)
    source_id: str = Field(description="Source record this plan applies to.")
    context_package_id: str | None = Field(
        default=None,
        description="Context package used to decide this plan.",
    )
    execution_mode: ExtractionExecutionMode = Field(
        default=ExtractionExecutionMode.FOCUSED_EXTRACTION,
        description="Backend execution mode selected after source and context review.",
    )
    reason: str | None = Field(
        default=None,
        description="Concise reason for the selected plan and execution mode.",
    )
    tasks: list[ExtractionTask] = Field(default_factory=list)
    clarification: ClarificationRequest | None = Field(
        default=None,
        description="Blocking clarification required before extraction can continue.",
    )
    context_gaps: list[str] = Field(
        default_factory=list,
        description="Missing context that future agents may retrieve before extraction.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateBase(IngestionModel):
    local_ref: str = Field(
        description=(
            "LLM-safe local reference such as CANDIDATE_PERSON_001. "
            "Use this instead of raw UUIDs inside extraction tasks."
        ),
    )
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional confidence only when a process can justify it.",
    )
    ambiguity_flags: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateEntity(CandidateBase):
    candidate_id: str = Field(default_factory=new_uuid)
    entity_type: str = Field(description="Target graph label, validated against graph registry.")
    display_name: str | None = Field(
        default=None,
        description="Best human-readable name for display and retrieval.",
    )
    description: str | None = Field(
        default=None,
        description="Memory-bearing description when available.",
    )
    aliases: list[str] = Field(default_factory=list)
    typed_properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Typed graph properties to place on the future node.",
    )
    affective_fields: AffectiveFields | None = Field(
        default=None,
        description="Affective or perceptual content carried by this entity.",
    )
    missing_fields: list[str] = Field(default_factory=list)


class CandidateRelationship(CandidateBase):
    candidate_relationship_id: str = Field(default_factory=new_uuid)
    relationship_type: str = Field(description="Target graph relationship type.")
    from_ref: str = Field(description="Source endpoint ref, usually a candidate ref or alias.")
    to_ref: str = Field(description="Target endpoint ref, usually a candidate ref or alias.")
    properties: dict[str, Any] = Field(default_factory=dict)
    affective_fields: AffectiveFields | None = None
    temporal_scope: TemporalScope | None = None


class CandidateClaim(CandidateBase):
    candidate_claim_id: str = Field(default_factory=new_uuid)
    claim_type: str | None = Field(default=None)
    text: str = Field(description="Atomic claim text to preserve as a graph claim.")
    about_refs: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    valid_from: str | None = None
    valid_to: str | None = None
    contradiction_refs: list[str] = Field(default_factory=list)


class CandidatePerception(CandidateBase):
    candidate_perception_id: str = Field(default_factory=new_uuid)
    target_ref: str = Field(description="Candidate ref or graph alias being perceived.")
    description: str = Field(description="Description of the user's perception.")
    perception_type: str | None = None
    emotional_summary: str | None = None
    emotional_valence: str | None = None
    emotional_intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    emotion_tags: list[str] = Field(default_factory=list)
    original_user_words: str | None = None
    source_kind: str | None = None
    temporal_scope: TemporalScope | None = None


class CandidateRelationshipContext(CandidateBase):
    candidate_relationship_context_id: str = Field(default_factory=new_uuid)
    from_ref: str = Field(description="First endpoint of the relationship context.")
    to_ref: str = Field(description="Second endpoint of the relationship context.")
    relationship_type: str | None = Field(default=None)
    status: str | None = Field(default=None)
    closeness: str | None = Field(default=None)
    description: str | None = Field(default=None)
    emotional_summary: str | None = None
    emotional_valence: str | None = None
    emotional_intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    emotion_tags: list[str] = Field(default_factory=list)
    original_user_words: str | None = None
    temporal_scope: TemporalScope | None = None


class CandidateMetadataPatch(CandidateBase):
    patch_id: str = Field(default_factory=new_uuid)
    target_ref: str = Field(description="Candidate ref or graph alias receiving the patch.")
    operation: Literal["set", "append", "remove"] = Field(
        description="Patch operation requested by the extraction step.",
    )
    path: str = Field(description="Dot-separated target field path.")
    value: Any = Field(default=None)
    previous_value: Any = Field(default=None)
    reason: str | None = Field(default=None)


CandidateOutput: TypeAlias = (
    CandidateEntity
    | CandidateRelationship
    | CandidateClaim
    | CandidatePerception
    | CandidateRelationshipContext
    | CandidateMetadataPatch
)


class CandidateMemoryGraph(IngestionModel):
    candidate_graph_id: str = Field(default_factory=new_uuid)
    source_id: str = Field(description="Source record used to create this candidate graph.")
    extraction_plan_id: str | None = None
    candidate_entities: list[CandidateEntity] = Field(default_factory=list)
    candidate_relationships: list[CandidateRelationship] = Field(default_factory=list)
    candidate_claims: list[CandidateClaim] = Field(default_factory=list)
    candidate_perceptions: list[CandidatePerception] = Field(default_factory=list)
    candidate_relationship_contexts: list[CandidateRelationshipContext] = Field(
        default_factory=list,
    )
    candidate_metadata_patches: list[CandidateMetadataPatch] = Field(default_factory=list)
    local_ref_map: dict[str, str] = Field(
        default_factory=dict,
        description="Map from LLM-safe local refs to candidate ids.",
    )
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    ambiguity_flags: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResolutionDecision(IngestionModel):
    decision_id: str = Field(default_factory=new_uuid)
    candidate_ref: str = Field(description="Candidate local ref this decision applies to.")
    decision_type: ResolutionDecisionType = Field(description="Resolution action chosen.")
    target_entity_id: str | None = Field(
        default=None,
        description="Existing graph id when matching or merging.",
    )
    scores: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    decided_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphNodeWrite(IngestionModel):
    local_ref: str = Field(description="Candidate or graph alias represented by this write.")
    label: str = Field(description="Graph node label validated before execution.")
    properties: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    idempotency_key: str | None = None


class GraphRelationshipWrite(IngestionModel):
    local_ref: str = Field(description="Local write reference.")
    relationship_type: str = Field(
        description="Graph relationship type validated before execution.",
    )
    from_ref: str = Field(description="Source endpoint ref.")
    to_ref: str = Field(description="Target endpoint ref.")
    properties: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    idempotency_key: str | None = None


class GraphWritePlan(IngestionModel):
    write_plan_id: str = Field(default_factory=new_uuid)
    source_id: str
    status: GraphWritePlanStatus = Field(default=GraphWritePlanStatus.DRAFT)
    nodes_to_create: list[GraphNodeWrite] = Field(default_factory=list)
    nodes_to_update: list[GraphNodeWrite] = Field(default_factory=list)
    relationships_to_create: list[GraphRelationshipWrite] = Field(default_factory=list)
    relationships_to_update: list[GraphRelationshipWrite] = Field(default_factory=list)
    claims_to_create: list[GraphNodeWrite] = Field(default_factory=list)
    perceptions_to_create: list[GraphNodeWrite] = Field(default_factory=list)
    relationship_contexts_to_create: list[GraphNodeWrite] = Field(default_factory=list)
    metadata_patches: list[CandidateMetadataPatch] = Field(default_factory=list)
    evidence_links: list[EvidenceRef] = Field(default_factory=list)
    idempotency_keys: list[str] = Field(default_factory=list)
    resolution_decisions: list[ResolutionDecision] = Field(default_factory=list)
    validation_errors: list[ValidationIssue] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestionContextPackage(IngestionModel):
    context_package_id: str = Field(default_factory=new_uuid)
    source_id: str
    aliases: dict[str, str] = Field(
        default_factory=dict,
        description="LLM-facing aliases mapped to internal graph ids.",
    )
    entities: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationIssue(IngestionModel):
    field_path: str = Field(description="Path to the invalid or risky field.")
    message: str = Field(description="Verbose message that can guide an LLM tool retry.")
    code: str = Field(description="Stable machine-readable validation code.")
    severity: Literal["error", "warning"] = "error"
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(IngestionModel):
    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)

    @classmethod
    def ok(cls) -> ValidationResult:
        return cls(is_valid=True)

    @classmethod
    def from_issues(cls, issues: list[ValidationIssue]) -> ValidationResult:
        return cls(
            is_valid=not any(issue.severity == "error" for issue in issues),
            issues=issues,
        )


class IngestionResult(IngestionModel):
    ingestion_id: str = Field(default_factory=new_uuid)
    source_id: str
    status: IngestionStatus
    mention_scan: MentionScan | None = None
    extraction_plan: ExtractionPlan | None = None
    candidate_graph: CandidateMemoryGraph | None = None
    clarification: ClarificationRequest | None = None
    write_plan: GraphWritePlan | None = None
    validation_errors: list[ValidationIssue] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
