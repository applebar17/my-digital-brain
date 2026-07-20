from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.core.owner_context import OwnerSnapshot
from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.contracts.candidates import (
    CandidateEntity,
    CandidateMemoryGraph,
    CandidateOutput,
)
from my_digital_brain.ingestion.contracts.context import GraphContextPack, GraphContextPackView
from my_digital_brain.ingestion.contracts.identity_resolution import EntityLookupContextPacket
from my_digital_brain.ingestion.contracts.planning import (
    ClarificationRequest,
    ExtractionPlan,
)
from my_digital_brain.ingestion.contracts.memory_logs import MemoryLog
from my_digital_brain.ingestion.contracts.refined_drafts import (
    EntityIngestionPlanDraft,
    IngestionReasoningCheckpointDraft,
    MemoryLogIngestionPlanDraft,
    RelationshipIngestionPlanDraft,
)
from my_digital_brain.ingestion.contracts.resolution import ResolvedEntityMap
from my_digital_brain.ingestion.contracts.validation import ValidationIssue
from my_digital_brain.ingestion.contracts.write_plan import GraphWritePlan
from my_digital_brain.ingestion.enums import IngestionStatus


class IngestionContextPackage(IngestionModel):
    context_package_id: str = Field(default_factory=new_uuid)
    source_id: str
    aliases: dict[str, str] = Field(
        default_factory=dict,
        description="Backend alias projection mapped to internal graph ids.",
    )
    reference_registry_snapshot: dict[str, Any] = Field(
        default_factory=dict,
        description="Backend-only run reference registry snapshot.",
    )
    identity_lookup_packets: list[EntityLookupContextPacket] = Field(
        default_factory=list,
        description="Backend-built candidate lookup packets available to extraction.",
    )
    entities: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    owner_snapshot: OwnerSnapshot | None = Field(default=None)


class IngestionResult(IngestionModel):
    ingestion_id: str = Field(default_factory=new_uuid)
    source_id: str
    status: IngestionStatus
    extraction_plan: ExtractionPlan | None = None
    graph_context_pack: GraphContextPack | None = None
    graph_context_views: dict[str, GraphContextPackView] = Field(default_factory=dict)
    reasoning: IngestionReasoningCheckpointDraft | None = None
    entity_plan: EntityIngestionPlanDraft | None = None
    entity_extraction_plan: ExtractionPlan | None = None
    entity_candidates: list[CandidateEntity] = Field(default_factory=list)
    entity_candidate_graph: CandidateMemoryGraph | None = None
    supplemental_entity_plans: list[EntityIngestionPlanDraft] = Field(default_factory=list)
    supplemental_entity_extraction_plans: list[ExtractionPlan] = Field(default_factory=list)
    supplemental_entity_candidates: list[CandidateEntity] = Field(default_factory=list)
    resolved_entity_map: ResolvedEntityMap | None = None
    memory_log_plan: MemoryLogIngestionPlanDraft | None = None
    memory_log_extraction_plan: ExtractionPlan | None = None
    memory_logs: list[MemoryLog] = Field(default_factory=list)
    relationship_plan: RelationshipIngestionPlanDraft | None = None
    relationship_extraction_plan: ExtractionPlan | None = None
    relationship_candidates: list[CandidateOutput] = Field(default_factory=list)
    candidate_graph: CandidateMemoryGraph | None = None
    clarification: ClarificationRequest | None = None
    write_plan: GraphWritePlan | None = None
    validation_errors: list[ValidationIssue] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestionSessionSnapshot(IngestionModel):
    session_id: str = Field(default_factory=new_uuid)
    source_id: str
    status: IngestionStatus
    pending_question: str | None = None
    reference_registry_snapshot: dict[str, Any] = Field(default_factory=dict)
    candidate_graph_snapshot: dict[str, Any] = Field(default_factory=dict)
    write_plan_snapshot: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
