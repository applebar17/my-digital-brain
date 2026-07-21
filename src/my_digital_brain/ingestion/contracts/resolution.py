from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

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
    clarifications: list[ClarificationRequest] = Field(
        default_factory=list,
        description="All clarification requests emitted by the current resolution step.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _synchronize_clarifications(self) -> "ResolutionResult":
        if self.clarification is not None and not self.clarifications:
            self.clarifications = [self.clarification]
        elif self.clarifications and self.clarification is None:
            self.clarification = self.clarifications[0]
        return self


class ResolvedEntityStatus(StrEnum):
    MATCHED_EXISTING = "matched_existing"
    STAGED_CREATE = "staged_create"
    STAGED_UPDATE = "staged_update"
    REJECTED = "rejected"
    PENDING_DUPLICATE_REVIEW = "pending_duplicate_review"


class ResolvedEntityMapEntry(IngestionModel):
    local_ref: str = Field(description="Planner or candidate local ref for this entity.")
    status: ResolvedEntityStatus = Field(description="Resolution status for this local ref.")
    display_label: str | None = Field(
        default=None,
        description="Human-readable label for planning and relationship handoff.",
    )
    entity_type: str | None = Field(
        default=None,
        description="Entity type label when known.",
    )
    graph_alias: str | None = Field(
        default=None,
        description="Optional graph alias for an existing or staged entity.",
    )
    duplicate_notes: list[str] = Field(
        default_factory=list,
        description="Lightweight notes about suspected duplicate matches.",
    )
    ambiguity_notes: list[str] = Field(
        default_factory=list,
        description="Lightweight notes about unresolved ambiguity.",
    )
    resolution_reason: str | None = Field(
        default=None,
        description="Short reason for the status selected by resolution.",
    )

    @property
    def is_relationship_usable(self) -> bool:
        return str(self.status) in {
            ResolvedEntityStatus.MATCHED_EXISTING.value,
            ResolvedEntityStatus.STAGED_CREATE.value,
            ResolvedEntityStatus.STAGED_UPDATE.value,
        }

    @property
    def relationship_ref(self) -> str | None:
        if not self.is_relationship_usable:
            return None
        return self.graph_alias or self.local_ref


class ResolvedEntityMap(IngestionModel):
    resolved_entity_map_id: str = Field(
        default_factory=new_uuid,
        description="Backend correlation id for this entity-resolution map.",
    )
    entries: list[ResolvedEntityMapEntry] = Field(
        default_factory=list,
        description="Resolved, staged, rejected, or review-pending entity refs.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Lightweight backend notes for later relationship planning.",
    )

    @property
    def relationship_usable_refs(self) -> dict[str, str]:
        return {
            entry.local_ref: entry.relationship_ref
            for entry in self.entries
            if entry.relationship_ref is not None
        }

    def entry_for(self, local_ref: str) -> ResolvedEntityMapEntry | None:
        return next((entry for entry in self.entries if entry.local_ref == local_ref), None)

    def relationship_ref_for(self, local_ref: str) -> str | None:
        entry = self.entry_for(local_ref)
        if entry is None:
            return None
        return entry.relationship_ref
