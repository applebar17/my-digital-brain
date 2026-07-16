from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from my_digital_brain.agentic.base import AgenticModel, utc_now
from my_digital_brain.agentic.contexts import ConversationContext, ToolResultContext
from my_digital_brain.core.ids import new_uuid
from my_digital_brain.core.owner_context import OwnerSnapshot
from my_digital_brain.core.profile_context import (
    OwnerProfilePurpose,
    OwnerProfileSnapshot,
)


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
    owner_snapshot: OwnerSnapshot | None = None
    approved_owner_profile: OwnerProfileSnapshot | None = None
    profile_purpose: OwnerProfilePurpose | None = None

    @model_validator(mode="after")
    def _validate_profile_scope(self) -> "PlanningTransformContext":
        if (self.approved_owner_profile is None) != (self.profile_purpose is None):
            raise ValueError(
                "approved_owner_profile and profile_purpose must be supplied together"
            )
        return self

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
                "owner_snapshot": self.owner_snapshot,
                **(
                    {
                        "profile_purpose": self.profile_purpose,
                        "approved_owner_profile": self.approved_owner_profile,
                    }
                    if self.profile_purpose is not None
                    else {}
                ),
            },
        )

    def system_prompt_payload(self) -> dict[str, Any]:
        """Return the intentionally small packet formatted into system prompts."""

        scope = str(self.input_context.get("planning_scope") or "")
        return _compact_prompt_payload(
            {
                "purpose": _prompt_purpose(self.purpose, self.input_context),
                "task_context": _prompt_task_context(
                    self.input_context,
                    current_time=self.current_time,
                    timezone=self.timezone,
                ),
                "reasoning_notes": _prompt_reasoning_notes(
                    self.reasoning_artifact,
                    scope=scope,
                ),
                "owner_snapshot": self.owner_snapshot,
                **(
                    {
                        "profile_purpose": self.profile_purpose,
                        "approved_owner_profile": self.approved_owner_profile,
                    }
                    if self.profile_purpose is not None
                    else {}
                ),
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


def _prompt_purpose(
    purpose: PlanningPurposeGuidelines,
    input_context: dict[str, Any],
) -> dict[str, Any]:
    instructions = list(purpose.instructions)
    rules = input_context.get("rules")
    if isinstance(rules, list):
        instructions.extend(str(rule) for rule in rules if rule)
    return {
        key: value
        for key, value in {
            "goal": purpose.goal,
            "focus_areas": list(purpose.focus_areas),
            "instructions": list(dict.fromkeys(instructions)),
        }.items()
        if value not in (None, "", [], {})
    }


def _prompt_task_context(
    input_context: dict[str, Any],
    *,
    current_time: datetime,
    timezone: str,
) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "planning_scope": input_context.get("planning_scope"),
        "graph_context_view": input_context.get("graph_context_view"),
        "entity_packet": input_context.get("entity_packet"),
        "memory_log_packet": input_context.get("memory_log_packet"),
        "time": {
            "current_time": current_time,
            "timezone": timezone,
        },
    }
    if input_context.get("planning_scope") == "memory_log_extraction":
        return _compact_prompt_payload(packet)
    current_action = input_context.get("planning_action")
    if current_action not in (None, "", [], {}):
        packet["current_action"] = _prompt_current_action(current_action)
    current_target = (
        input_context.get("planned_memory_log")
        or input_context.get("missing_entity_required")
    )
    if current_target not in (None, "", [], {}):
        packet["current_target"] = current_target
    current_targets = input_context.get("current_targets")
    if current_targets not in (None, "", [], {}):
        packet["current_targets"] = current_targets
    expected_local_ref = input_context.get("expected_local_ref")
    if expected_local_ref not in (None, "", [], {}):
        packet["expected_local_ref"] = expected_local_ref
    expected_local_refs = input_context.get("expected_local_refs")
    if expected_local_refs not in (None, "", [], {}):
        packet["expected_local_refs"] = expected_local_refs
    memory_log_index = input_context.get("memory_log_index")
    if memory_log_index not in (None, "", [], {}):
        packet["target_index"] = memory_log_index
    return _compact_prompt_payload(packet)


def _prompt_current_action(action: Any) -> Any:
    action_payload = _compact_prompt_payload(action)
    if not isinstance(action_payload, dict):
        return action_payload
    return {
        key: value
        for key, value in {
            "goal": action_payload.get("goal"),
            "local_ref": action_payload.get("local_ref"),
            "relationship_intent": action_payload.get("relationship_intent"),
            "storage_shape": action_payload.get("storage_shape"),
            "from_ref": action_payload.get("from_ref"),
            "to_ref": action_payload.get("to_ref"),
            "depends_on": action_payload.get("depends_on"),
            "notes": action_payload.get("notes"),
        }.items()
        if value not in (None, "", [], {})
    }


_PROMPT_REASONING_KEYS_BY_SCOPE = {
    "entities_only": {
        "summary",
        "entity_notes",
        "alias_notes",
        "duplicate_notes",
        "node_vs_detail_notes",
        "user_owner_notes",
        "context_gaps",
        "clarification_candidates",
    },
    "memory_logs_only": {
        "summary",
        "entity_notes",
        "relationship_notes",
        "user_owner_notes",
        "context_gaps",
        "clarification_candidates",
    },
    "memory_log_extraction": {
        "summary",
        "entity_notes",
        "relationship_notes",
        "user_owner_notes",
        "context_gaps",
        "clarification_candidates",
    },
    "relationships_only": {
        "summary",
        "alias_notes",
        "relationship_notes",
        "duplicate_notes",
        "user_owner_notes",
        "context_gaps",
        "clarification_candidates",
    },
    "missing_entity_only": {
        "summary",
        "entity_notes",
        "alias_notes",
        "duplicate_notes",
        "context_gaps",
        "clarification_candidates",
    },
}


def _prompt_reasoning_notes(
    reasoning_artifact: dict[str, Any] | None,
    *,
    scope: str,
) -> dict[str, Any] | None:
    if not isinstance(reasoning_artifact, dict):
        return reasoning_artifact
    keys = _PROMPT_REASONING_KEYS_BY_SCOPE.get(
        scope,
        {
            "summary",
            "context_gaps",
            "clarification_candidates",
        },
    )
    return {
        key: _compact_prompt_payload(value)
        for key, value in reasoning_artifact.items()
        if key in keys and value not in (None, "", [], {})
    }
