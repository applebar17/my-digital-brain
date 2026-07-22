"""Minimal toolboxes used by identity-resolution proposal steps."""

from __future__ import annotations

from my_digital_brain.agentic.tools.specs import (
    array_property,
    object_property,
    optional_string_property,
    string_property,
    tool_spec,
)
from my_digital_brain.ai.tools import ToolBox, build_tool_index
from my_digital_brain.ingestion.contracts import ResolutionStep, ResolutionToolName, tools_for_step


def build_resolution_toolbox(step: ResolutionStep | str) -> ToolBox:
    """Build the smallest action toolbox for one resolution/extraction step."""

    resolved_step = ResolutionStep(step)
    tools = [_tool_specs[name] for name in tools_for_step(resolved_step)]
    return ToolBox(
        name=f"ingestion:resolution:{resolved_step.value}",
        tools=tools,
        tools_by_name=build_tool_index(tools),
    )


def resolution_toolbox_for_task(task_type: str) -> ToolBox | None:
    normalized = str(task_type).lower()
    if normalized in {
        "person",
        "place",
        "event",
        "organization",
        "object",
        "animal",
        "social_circle",
        "topic",
        "link",
    }:
        return build_resolution_toolbox(ResolutionStep.NODE)
    if normalized in {"memory_log", "profile_memory", "claim", "perception", "metadata_patch"}:
        return build_resolution_toolbox(ResolutionStep.MEMORY)
    if normalized in {"relationship", "relationship_context", "relationship_state"}:
        return build_resolution_toolbox(ResolutionStep.RELATIONSHIP)
    return None


def _action_properties() -> dict[str, dict]:
    return {
        "candidate_ref": string_property("Candidate ref supplied in the current context."),
        "target_ref": optional_string_property("Existing supplied ref to update, when applicable."),
        "from_ref": optional_string_property(
            "Supplied source endpoint ref, for relationship actions."
        ),
        "to_ref": optional_string_property(
            "Supplied target endpoint ref, for relationship actions."
        ),
        "payload": object_property(
            "Sparse structured patch for the candidate or graph object. "
            "When a clarification changes a value, include the changed field "
            "here; do not put it only in reason."
        ),
        "reason": optional_string_property("Short source-grounded reason for the action."),
        "evidence_refs": array_property("Supplied evidence refs supporting the action."),
    }


def _spec(
    name: ResolutionToolName,
    description: str,
    fields: tuple[str, ...],
) -> dict:
    properties = _action_properties()
    return tool_spec(
        name.value,
        description,
        properties={field: properties[field] for field in fields},
    )


_tool_specs = {
    ResolutionToolName.ASK_CLARIFICATION: tool_spec(
        ResolutionToolName.ASK_CLARIFICATION.value,
        (
            "Ask the user for clarification when the supplied context cannot support "
            "a safe action. This interrupts the current step and is not a graph action."
        ),
        properties={
            "candidate_ref": string_property("Candidate ref supplied in the current context."),
            "question": string_property("User-facing clarification question."),
            "options": array_property("Short answer options."),
            "reason": optional_string_property("Why the current context is insufficient."),
            "evidence_refs": array_property("Supplied evidence refs supporting the question."),
        },
    ),
    ResolutionToolName.CREATE_NODE: _spec(
        ResolutionToolName.CREATE_NODE,
        (
            "Propose a new non-owner graph node. Use payload as a sparse patch; "
            "after clarification, include the clarified identity fields such as "
            "display_name in payload."
        ),
        ("candidate_ref", "payload", "reason", "evidence_refs"),
    ),
    ResolutionToolName.UPDATE_NODE: _spec(
        ResolutionToolName.UPDATE_NODE,
        (
            "Propose an additive update to one supplied existing node. Do not place "
            "stable traits directly on Person. Use payload for every explicit "
            "field change, including values supplied by clarification."
        ),
        ("candidate_ref", "target_ref", "payload", "reason", "evidence_refs"),
    ),
    ResolutionToolName.CREATE_MEMORY: _spec(
        ResolutionToolName.CREATE_MEMORY,
        "Propose a new memory record linked to supplied refs, preserving source evidence.",
        ("candidate_ref", "target_ref", "payload", "reason", "evidence_refs"),
    ),
    ResolutionToolName.UPDATE_MEMORY: _spec(
        ResolutionToolName.UPDATE_MEMORY,
        "Propose an additive update to one supplied memory record.",
        ("candidate_ref", "target_ref", "payload", "reason", "evidence_refs"),
    ),
    ResolutionToolName.CREATE_RELATIONSHIP: _spec(
        ResolutionToolName.CREATE_RELATIONSHIP,
        "Propose a relationship between two supplied endpoint refs.",
        ("candidate_ref", "from_ref", "to_ref", "payload", "reason", "evidence_refs"),
    ),
    ResolutionToolName.UPDATE_RELATIONSHIP: _spec(
        ResolutionToolName.UPDATE_RELATIONSHIP,
        "Propose an update to a relationship using supplied endpoint and target refs.",
        ("candidate_ref", "target_ref", "from_ref", "to_ref", "payload", "reason", "evidence_refs"),
    ),
    ResolutionToolName.DEFER_OR_IGNORE: _spec(
        ResolutionToolName.DEFER_OR_IGNORE,
        (
            "Defer or ignore the candidate only when the user explicitly asks not to "
            "save or to defer it. Otherwise use the best supported ambiguous identity "
            "when clarification does not provide more detail."
        ),
        ("candidate_ref", "reason", "evidence_refs"),
    ),
}
