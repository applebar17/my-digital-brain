from __future__ import annotations

from typing import Any

from pydantic import Field

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.contracts.candidates import CandidateMetadataPatch
from my_digital_brain.ingestion.contracts.resolution import ResolutionDecision
from my_digital_brain.ingestion.contracts.source import EvidenceRef
from my_digital_brain.ingestion.contracts.validation import ValidationIssue
from my_digital_brain.ingestion.enums import GraphWritePlanStatus


class GraphNodeWrite(IngestionModel):
    local_ref: str = Field(description="Candidate or graph alias represented by this write.")
    label: str = Field(description="Graph node label validated before execution.")
    target_ref: str | None = Field(
        default=None,
        description="Existing graph id or alias when this write patches an existing node.",
    )
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
    memory_logs_to_create: list[GraphNodeWrite] = Field(default_factory=list)
    metadata_patches: list[CandidateMetadataPatch] = Field(default_factory=list)
    evidence_links: list[EvidenceRef] = Field(default_factory=list)
    idempotency_keys: list[str] = Field(default_factory=list)
    resolution_decisions: list[ResolutionDecision] = Field(default_factory=list)
    validation_errors: list[ValidationIssue] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
