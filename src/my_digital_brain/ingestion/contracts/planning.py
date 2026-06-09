from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, Field, model_validator

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.enums import (
    ClarificationStatus,
    ExtractionExecutionMode,
    ExtractionTaskType,
)


class ClarificationRequest(IngestionModel):
    clarification_id: str = Field(default_factory=new_uuid)
    doubt: str = Field(
        description=(
            "Backend-facing clarification doubt. State the uncertainty to resolve; "
            "do not phrase it as an authoritative user question."
        ),
        validation_alias=AliasChoices("doubt", "question"),
        serialization_alias="doubt",
    )
    reason: str = Field(description="Why this clarification may be needed.")
    target_refs: list[str] = Field(
        default_factory=list,
        description="Candidate refs, graph aliases, or source refs affected by the doubt.",
    )
    options: str | None = Field(
        default=None,
        description=(
            "Concise description of plausible interpretations or answer directions "
            "supported by context. Not exhaustive and not authoritative."
        ),
    )
    blocking: bool = Field(
        default=True,
        description="Whether ingestion should wait before producing graph write candidates.",
    )
    status: ClarificationStatus = Field(default=ClarificationStatus.PROPOSED)
    created_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

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
