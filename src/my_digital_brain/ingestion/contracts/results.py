from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.contracts.candidates import CandidateMemoryGraph
from my_digital_brain.ingestion.contracts.planning import (
    ClarificationRequest,
    ExtractionPlan,
    MentionScan,
)
from my_digital_brain.ingestion.contracts.validation import ValidationIssue
from my_digital_brain.ingestion.contracts.write_plan import GraphWritePlan
from my_digital_brain.ingestion.enums import IngestionStatus


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


class IngestionSessionSnapshot(IngestionModel):
    session_id: str = Field(default_factory=new_uuid)
    source_id: str
    status: IngestionStatus
    pending_question: str | None = None
    candidate_graph_snapshot: dict[str, Any] = Field(default_factory=dict)
    write_plan_snapshot: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
