from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.enums import (
    ClarificationStatus,
    ExtractionExecutionMode,
    ExtractionTaskType,
    MentionKind,
)


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
