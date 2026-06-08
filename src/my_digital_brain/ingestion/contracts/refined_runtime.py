from __future__ import annotations

from typing import Any

from pydantic import Field

from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.contracts.candidates import CandidateEntity, CandidateMemoryGraph
from my_digital_brain.ingestion.contracts.context import GraphContextPack, GraphContextPackView
from my_digital_brain.ingestion.contracts.planning import ClarificationRequest, ExtractionPlan
from my_digital_brain.ingestion.contracts.refined_drafts import (
    EntityIngestionPlanDraft,
    IngestionReasoningCheckpointDraft,
    RelationshipIngestionPlanDraft,
)
from my_digital_brain.ingestion.contracts.resolution import ResolvedEntityMap
from my_digital_brain.ingestion.contracts.validation import ValidationIssue
from my_digital_brain.ingestion.enums import IngestionStatus


class RefinedIngestionResult(IngestionModel):
    source_id: str = Field(description="Source processed by the refined ingestion runtime.")
    status: IngestionStatus = Field(description="Current terminal status for this wave slice.")
    graph_context_pack: GraphContextPack | None = None
    graph_context_views: dict[str, GraphContextPackView] = Field(default_factory=dict)
    reasoning: IngestionReasoningCheckpointDraft | None = None
    entity_plan: EntityIngestionPlanDraft | None = None
    entity_extraction_plan: ExtractionPlan | None = None
    entity_candidates: list[CandidateEntity] = Field(default_factory=list)
    entity_candidate_graph: CandidateMemoryGraph | None = None
    resolved_entity_map: ResolvedEntityMap | None = None
    relationship_plan: RelationshipIngestionPlanDraft | None = None
    clarification: ClarificationRequest | None = None
    validation_errors: list[ValidationIssue] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
