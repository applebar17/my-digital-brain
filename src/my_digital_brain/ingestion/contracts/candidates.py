from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import Field, model_validator

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.contracts.memory_logs import MemoryLog
from my_digital_brain.ingestion.contracts.shared import AffectiveFields, TemporalScope
from my_digital_brain.ingestion.contracts.source import EvidenceRef


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
    relationship_kind: str | None = None
    relationship_detail: str | None = None
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
    relationship_kind: str | None = None
    relationship_detail: str | None = None
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


class CandidateProfileMemory(CandidateBase):
    """Proposed durable self-information; the backend owns its graph edge."""

    profile_key: str
    category: str
    value: str
    description: str = ""
    owner_ref: Literal["OWNER"] = "OWNER"
    original_user_words: str
    stability: Literal["recurring", "stable", "user_confirmed"] = "stable"
    visibility: Literal["hidden", "retrievable", "prompt_allowed"] = "hidden"
    assertion_mode: Literal["explicit", "inferred"] = "explicit"
    reason: str

    @model_validator(mode="after")
    def _validate_profile_memory(self) -> "CandidateProfileMemory":
        if not self.original_user_words.strip():
            raise ValueError("Profile memory requires original_user_words.")
        if self.assertion_mode == "inferred":
            self.requires_confirmation = True
            if self.stability == "user_confirmed":
                raise ValueError("Inferred profile memory cannot be user-confirmed.")
        return self


CandidateOutput: TypeAlias = (
    CandidateEntity
    | CandidateRelationship
    | CandidateClaim
    | CandidatePerception
    | CandidateRelationshipContext
    | CandidateMetadataPatch
    | CandidateProfileMemory
    | MemoryLog
)


class CandidateEntityBatch(IngestionModel):
    candidates: list[CandidateEntity] = Field(default_factory=list)


class CandidateRelationshipBatch(IngestionModel):
    candidates: list[CandidateRelationship] = Field(default_factory=list)


class CandidateClaimBatch(IngestionModel):
    candidates: list[CandidateClaim] = Field(default_factory=list)


class CandidatePerceptionBatch(IngestionModel):
    candidates: list[CandidatePerception] = Field(default_factory=list)


class CandidateRelationshipContextBatch(IngestionModel):
    candidates: list[CandidateRelationshipContext] = Field(default_factory=list)


class CandidateMetadataPatchBatch(IngestionModel):
    candidates: list[CandidateMetadataPatch] = Field(default_factory=list)


class CandidateProfileMemoryBatch(IngestionModel):
    candidates: list[CandidateProfileMemory] = Field(default_factory=list)


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
    memory_logs: list[MemoryLog] = Field(
        default_factory=list,
        description=(
            "Backend-enriched MemoryLog records to create as lightweight memory atoms. "
            "These are not generic entity candidates."
        ),
    )
    candidate_metadata_patches: list[CandidateMetadataPatch] = Field(default_factory=list)
    candidate_profile_memories: list[CandidateProfileMemory] = Field(default_factory=list)
    local_ref_map: dict[str, str] = Field(
        default_factory=dict,
        description="Map from LLM-safe local refs to candidate ids.",
    )
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    ambiguity_flags: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
