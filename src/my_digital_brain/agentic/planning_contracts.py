from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from my_digital_brain.agentic.base import AgenticModel, utc_now
from my_digital_brain.agentic.contexts import ConversationContext, ToolResultContext
from my_digital_brain.core.ids import new_uuid


class PlanningPurposeGuidelines(AgenticModel):
    """Reusable planning intent supplied by the caller."""

    purpose_id: str = Field(
        default="general",
        description="Stable caller-defined purpose id for this planning transform.",
    )
    goal: str = Field(
        description="Planning goal in task language, independent from runtime wiring.",
    )
    focus_areas: list[str] = Field(
        default_factory=list,
        description="Specific aspects the planner should inspect while transforming input.",
    )
    instructions: list[str] = Field(
        default_factory=list,
        description="Task-specific planning instructions layered on top of the generic template.",
    )
    output_usage: str | None = Field(
        default=None,
        description="How the caller expects to consume the planning output.",
    )
    forbidden_assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions the planner must not make without supporting context.",
    )


class PlanningTransformContext(AgenticModel):
    """Generic, caller-shaped context for reusable planning transforms."""

    planning_id: str = Field(
        default_factory=new_uuid,
        description="Backend correlation id for this planning transform.",
    )
    purpose: PlanningPurposeGuidelines = Field(
        description="Reusable planning purpose and task-specific guidelines.",
    )
    input_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Caller-shaped context payload. Dedicated callers decide its structure.",
    )
    reasoning_artifact: dict[str, Any] | None = Field(
        default=None,
        description="Optional prior reasoning output that planning should consume.",
    )
    conversation: ConversationContext | None = Field(
        default=None,
        description="Optional rendered conversation context relevant to this planning step.",
    )
    current_time: datetime = Field(
        default_factory=utc_now,
        description="Backend-provided current time for temporal reasoning.",
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone the planner should use when interpreting relative time.",
    )
    prior_tool_outputs: list[ToolResultContext] = Field(
        default_factory=list,
        description="Optional prior tool outputs relevant to this planning transform.",
    )
    expected_output_schema: str | dict[str, Any] | None = Field(
        default=None,
        description=(
            "Caller-declared structured output schema name or compact schema payload. "
            "Callers may still request dedicated output models."
        ),
    )

    def model_facing_payload(self) -> dict[str, Any]:
        return _compact_prompt_payload(
            {
                "purpose": self.purpose,
                "input_context": self.input_context,
                "reasoning_artifact": self.reasoning_artifact,
                "conversation": self.conversation,
                "current_time": self.current_time,
                "timezone": self.timezone,
                "prior_tool_outputs": self.prior_tool_outputs,
                "expected_output_schema": self.expected_output_schema,
            },
        )


class PlanningActionContext(AgenticModel):
    """Default lightweight action shape for generic planning use."""

    action_ref: str = Field(
        description="Planner-scoped action handle such as ACTION_001.",
    )
    goal: str = Field(
        description="Short user-language goal for this planned action.",
    )
    action_kind: str | None = Field(
        default=None,
        description="Optional caller-defined action category.",
    )
    target_refs: list[str] = Field(
        default_factory=list,
        description="Input refs, candidate refs, or graph aliases this action concerns.",
    )
    evidence_text: str | None = Field(
        default=None,
        description="Source wording or compact context that motivates the action.",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="Earlier action_refs whose outputs are required.",
    )
    notes: str | None = Field(
        default=None,
        description="Short operational note for the caller.",
    )


class PlanningTransformResultContext(AgenticModel):
    """Default generic planning result for callers without a dedicated schema."""

    planning_id: str = Field(description="Planning transform id this result answers.")
    purpose_id: str = Field(description="Purpose id copied from the planning guidelines.")
    summary: str = Field(description="Concise summary of the planning decision.")
    actions: list[PlanningActionContext] = Field(
        default_factory=list,
        description="Planned actions when the caller can proceed.",
    )
    clarification_candidates: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Lightweight caller-shaped clarification candidates.",
    )
    context_gaps: list[str] = Field(
        default_factory=list,
        description="Missing context that blocks or weakens planning.",
    )
    recommended_next_action: str | None = Field(
        default=None,
        description="Optional backend-readable next action suggestion.",
    )

    @model_validator(mode="after")
    def _validate_useful_signal(self) -> "PlanningTransformResultContext":
        if not self.summary.strip():
            raise ValueError("Planning transform result requires a summary.")
        if not (
            self.actions
            or self.clarification_candidates
            or self.context_gaps
            or self.recommended_next_action
        ):
            raise ValueError("Planning transform result requires at least one useful signal.")
        return self


def _compact_prompt_payload(value: Any) -> Any:
    if hasattr(value, "model_facing_payload"):
        return _compact_prompt_payload(value.model_facing_payload())
    if hasattr(value, "model_dump"):
        return _compact_prompt_payload(value.model_dump(mode="json", exclude_none=True))
    if isinstance(value, dict):
        compacted = {
            key: _compact_prompt_payload(item)
            for key, item in value.items()
            if key != "metadata"
        }
        return {
            key: item
            for key, item in compacted.items()
            if item not in (None, "", [], {})
        }
    if isinstance(value, list):
        return [
            item
            for item in (_compact_prompt_payload(item) for item in value)
            if item not in (None, "", [], {})
        ]
    return value
