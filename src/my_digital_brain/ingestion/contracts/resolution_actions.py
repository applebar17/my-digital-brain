from __future__ import annotations

from enum import StrEnum
import re
from typing import Any

from pydantic import Field, model_validator

from my_digital_brain.ingestion.contracts.base import IngestionModel


class ResolutionStep(StrEnum):
    NODE = "node"
    MEMORY = "memory"
    RELATIONSHIP = "relationship"


class ResolutionToolName(StrEnum):
    ASK_CLARIFICATION = "ask_clarification"
    CREATE_NODE = "create_node"
    UPDATE_NODE = "update_node"
    CREATE_MEMORY = "create_memory"
    UPDATE_MEMORY = "update_memory"
    CREATE_RELATIONSHIP = "create_relationship"
    UPDATE_RELATIONSHIP = "update_relationship"
    DEFER_OR_IGNORE = "defer_or_ignore"


_TOOLS_BY_STEP: dict[ResolutionStep, tuple[ResolutionToolName, ...]] = {
    ResolutionStep.NODE: (
        ResolutionToolName.ASK_CLARIFICATION,
        ResolutionToolName.CREATE_NODE,
        ResolutionToolName.UPDATE_NODE,
        ResolutionToolName.DEFER_OR_IGNORE,
    ),
    ResolutionStep.MEMORY: (
        ResolutionToolName.ASK_CLARIFICATION,
        ResolutionToolName.CREATE_MEMORY,
        ResolutionToolName.UPDATE_MEMORY,
        ResolutionToolName.DEFER_OR_IGNORE,
    ),
    ResolutionStep.RELATIONSHIP: (
        ResolutionToolName.ASK_CLARIFICATION,
        ResolutionToolName.CREATE_RELATIONSHIP,
        ResolutionToolName.UPDATE_RELATIONSHIP,
        ResolutionToolName.DEFER_OR_IGNORE,
    ),
}

_MODEL_REF_RE = re.compile(
    r"^(?:OWNER|CANDIDATE_[A-Z][A-Z0-9_]*_[0-9]{3,6}|"
    r"(?:NODE|REL|MEMORY|CONTEXT|MEDIA|SOURCE|CLAIM)_[0-9]{6}|"
    r"(?:MEMORY_LOG|PROFILE)_[A-Z0-9_]*[0-9]{3,6})$",
)


def tools_for_step(step: ResolutionStep | str) -> tuple[ResolutionToolName, ...]:
    return _TOOLS_BY_STEP[ResolutionStep(step)]


class ResolutionToolAction(IngestionModel):
    """One model-requested action before backend reference translation."""

    step: ResolutionStep
    tool_name: ResolutionToolName
    candidate_ref: str = Field(min_length=1)
    target_ref: str | None = None
    from_ref: str | None = None
    to_ref: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    question: str | None = None
    options: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_shape(self) -> "ResolutionToolAction":
        allowed = tools_for_step(self.step)
        if self.tool_name not in allowed:
            raise ValueError(
                f"Tool '{self.tool_name}' is not available for {self.step} resolution."
            )
        for ref_name, ref in (
            ("candidate_ref", self.candidate_ref),
            ("target_ref", self.target_ref),
            ("from_ref", self.from_ref),
            ("to_ref", self.to_ref),
            *[(f"evidence_refs[{index}]", value) for index, value in enumerate(self.evidence_refs)],
        ):
            if ref is not None and not _MODEL_REF_RE.fullmatch(ref):
                raise ValueError(f"{ref_name} must be a supplied model-facing reference.")

        if self.tool_name == ResolutionToolName.ASK_CLARIFICATION:
            if not self.question or not self.question.strip():
                raise ValueError("ask_clarification requires a question.")
        elif self.tool_name in {
            ResolutionToolName.UPDATE_NODE,
            ResolutionToolName.UPDATE_MEMORY,
            ResolutionToolName.UPDATE_RELATIONSHIP,
        } and not self.target_ref:
            raise ValueError(f"{self.tool_name} requires target_ref.")

        if self.tool_name in {
            ResolutionToolName.CREATE_RELATIONSHIP,
            ResolutionToolName.UPDATE_RELATIONSHIP,
        } and (not self.from_ref or not self.to_ref):
            raise ValueError(f"{self.tool_name} requires from_ref and to_ref.")
        return self


class ResolutionToolActionBatch(IngestionModel):
    actions: list[ResolutionToolAction] = Field(default_factory=list)
