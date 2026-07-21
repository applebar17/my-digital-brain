from __future__ import annotations

from typing import Any

from pydantic import Field

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.enums import ExtractionExecutionMode, ExtractionTaskType


class ExtractionTask(IngestionModel):
    task_id: str = Field(default_factory=new_uuid)
    task_type: ExtractionTaskType = Field(
        description="Focused extraction task assigned by the planner.",
    )
    target_ref: str | None = Field(
        default=None,
        description="Candidate ref, graph alias, or source ref this task focuses on.",
    )
    evidence_text: str | None = Field(default=None)
    source_refs: list[str] = Field(default_factory=list)
    expected_output: str | None = Field(default=None)
    required_context_refs: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionPlan(IngestionModel):
    extraction_plan_id: str = Field(default_factory=new_uuid)
    source_id: str
    context_package_id: str | None = None
    execution_mode: ExtractionExecutionMode = ExtractionExecutionMode.FOCUSED_EXTRACTION
    reason: str | None = None
    tasks: list[ExtractionTask] = Field(default_factory=list)
    context_gaps: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
