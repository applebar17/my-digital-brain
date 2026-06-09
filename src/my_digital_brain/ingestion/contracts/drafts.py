from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import AliasChoices, Field, model_validator

from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.contracts.shared import AffectiveFields, TemporalScope
from my_digital_brain.ingestion.ontology import (
    LLMEntityType,
    LLMRelationshipType,
    RelationshipKind,
)


class EvidenceSpanDraft(IngestionModel):
    evidence_text: str | None = Field(
        default=None,
        description="Short source snippet that supports the extracted draft.",
    )
    span_start: int | None = Field(default=None, ge=0)
    span_end: int | None = Field(default=None, ge=0)


class PropertyDraft(IngestionModel):
    key: str = Field(description="Short backend-readable property key.")
    value_text: str | None = Field(
        default=None,
        description="Property value as text from the source or inferred from context.",
    )
    value_kind: Literal["text", "number", "boolean", "date", "list", "unknown"] = Field(
        default="text",
        description="Expected deterministic coercion kind for the property value.",
    )
    reason: str | None = Field(
        default=None,
        description="Why this property is useful enough to keep.",
    )


class ClarificationRequestDraft(IngestionModel):
    doubt: str = Field(
        description=(
            "Model-explained doubt that may require user clarification. State what is "
            "uncertain; do not phrase this as an authoritative question."
        ),
        validation_alias=AliasChoices("doubt", "question"),
        serialization_alias="doubt",
    )
    reason: str = Field(description="Why this clarification may be needed.")
    target_refs: list[str] = Field(
        default_factory=list,
        description="Candidate refs or graph aliases affected by the doubt.",
    )
    options: str | None = Field(
        default=None,
        description=(
            "Concise description of plausible interpretations or answer directions "
            "supported by context. Do not present these as exhaustive or authoritative."
        ),
    )
    blocking: bool = Field(
        default=True,
        description="Whether ingestion should wait before producing graph write candidates.",
    )

    @property
    def question(self) -> str:
        return self.doubt

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_payload(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        normalized.pop("free_text_allowed", None)
        options = normalized.get("options")
        if isinstance(options, list):
            normalized["options"] = "; ".join(str(option) for option in options if option)
        return normalized


class CandidateBaseDraft(IngestionModel):
    local_ref: str = Field(
        description=(
            "Scoped local reference such as CANDIDATE_PERSON_001 for later task outputs."
        ),
    )
    evidence: list[EvidenceSpanDraft] = Field(default_factory=list)
    ambiguity_flags: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False


class CandidateEntityDraft(CandidateBaseDraft):
    entity_type: LLMEntityType = Field(
        description="Allowed memory entity type. Use only enum values; do not invent labels.",
    )
    display_name: str | None = Field(
        default=None,
        description="Best human-readable name for display and retrieval.",
    )
    description: str | None = Field(
        default=None,
        description="Memory-bearing description when available.",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description=(
            "Alias or nickname hints for extraction, retrieval, resolution, and context "
            "building. Aliases do not define node identity and are not automatically "
            "writable node properties."
        ),
    )
    property_suggestions: list[PropertyDraft] = Field(default_factory=list)
    affective_fields: AffectiveFields | None = Field(
        default=None,
        description="Affective or perceptual content carried by this entity.",
    )
    missing_fields: list[str] = Field(default_factory=list)


class CandidateRelationshipDraft(CandidateBaseDraft):
    relationship_type: LLMRelationshipType = Field(
        description="Allowed graph relationship type. Use only enum values.",
    )
    from_ref: str = Field(description="Source endpoint ref, usually a candidate ref or alias.")
    to_ref: str = Field(description="Target endpoint ref, usually a candidate ref or alias.")
    relationship_kind: RelationshipKind | None = Field(
        default=None,
        description=(
            "Governed social relationship kind when relationship_type is "
            "RELATIONSHIP_WITH."
        ),
    )
    relationship_detail: str | None = Field(
        default=None,
        description="Source-grounded wording such as brother, girlfriend, or university friend.",
    )
    property_suggestions: list[PropertyDraft] = Field(default_factory=list)
    affective_fields: AffectiveFields | None = None
    temporal_scope: TemporalScope | None = None


class CandidateClaimDraft(CandidateBaseDraft):
    claim_type: str | None = Field(default=None)
    text: str = Field(description="Atomic claim text to preserve as a graph claim.")
    about_refs: list[str] = Field(default_factory=list)
    property_suggestions: list[PropertyDraft] = Field(default_factory=list)
    valid_from: str | None = None
    valid_to: str | None = None
    contradiction_refs: list[str] = Field(default_factory=list)


class CandidatePerceptionDraft(CandidateBaseDraft):
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


class CandidateRelationshipContextDraft(CandidateBaseDraft):
    from_ref: str = Field(description="First endpoint of the relationship context.")
    to_ref: str = Field(description="Second endpoint of the relationship context.")
    relationship_type: LLMRelationshipType | None = Field(default=None)
    relationship_kind: RelationshipKind | None = Field(default=None)
    relationship_detail: str | None = Field(default=None)
    status: str | None = Field(default=None)
    closeness: str | None = Field(default=None)
    description: str | None = Field(default=None)
    emotional_summary: str | None = None
    emotional_valence: str | None = None
    emotional_intensity: float | None = Field(default=None, ge=0.0, le=1.0)
    emotion_tags: list[str] = Field(default_factory=list)
    original_user_words: str | None = None
    temporal_scope: TemporalScope | None = None


class CandidateMetadataPatchDraft(CandidateBaseDraft):
    target_ref: str = Field(description="Candidate ref or graph alias receiving the patch.")
    operation: Literal["set", "append", "remove"] = Field(
        description="Patch operation requested by the extraction step.",
    )
    path: str = Field(description="Dot-separated target field path.")
    value_text: str | None = Field(default=None)
    previous_value_text: str | None = Field(default=None)
    value_kind: Literal["text", "number", "boolean", "date", "list", "unknown"] = Field(
        default="text",
    )
    reason: str | None = Field(default=None)


CandidateOutputDraft: TypeAlias = (
    CandidateEntityDraft
    | CandidateRelationshipDraft
    | CandidateClaimDraft
    | CandidatePerceptionDraft
    | CandidateRelationshipContextDraft
    | CandidateMetadataPatchDraft
)


class CandidateEntityDraftBatch(IngestionModel):
    candidates: list[CandidateEntityDraft] = Field(default_factory=list)


class CandidateRelationshipDraftBatch(IngestionModel):
    candidates: list[CandidateRelationshipDraft] = Field(default_factory=list)


class CandidateClaimDraftBatch(IngestionModel):
    candidates: list[CandidateClaimDraft] = Field(default_factory=list)


class CandidatePerceptionDraftBatch(IngestionModel):
    candidates: list[CandidatePerceptionDraft] = Field(default_factory=list)


class CandidateRelationshipContextDraftBatch(IngestionModel):
    candidates: list[CandidateRelationshipContextDraft] = Field(default_factory=list)


class CandidateMetadataPatchDraftBatch(IngestionModel):
    candidates: list[CandidateMetadataPatchDraft] = Field(default_factory=list)
