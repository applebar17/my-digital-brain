from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.contracts.planning import ClarificationRequest
from my_digital_brain.ingestion.enums import ResolutionDecisionType


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


class ResolutionResult(IngestionModel):
    decisions: list[ResolutionDecision] = Field(default_factory=list)
    clarification: ClarificationRequest | None = Field(
        default=None,
        description="Clarification needed before a safe graph write plan can be built.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
