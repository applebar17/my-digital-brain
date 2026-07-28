"""Backend interpretation of validated resolution actions for write planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from my_digital_brain.graph.constants import NORMALIZED_NAME_LABELS
from my_digital_brain.graph.utils import normalize_text
from my_digital_brain.ingestion.contracts import (
    GraphNodeWrite,
    GraphRelationshipWrite,
    ResolutionResult,
    ResolutionStep,
    ResolutionToolAction,
    ResolutionToolName,
)


@dataclass(frozen=True, slots=True)
class ResolutionWriteActions:
    """Validated action index; an absent index preserves pre-Wave-5 behavior."""

    actions: dict[tuple[ResolutionStep, str], ResolutionToolAction]

    @classmethod
    def from_result(cls, result: ResolutionResult) -> ResolutionWriteActions | None:
        raw_actions = result.metadata.get("validated_tool_actions")
        if raw_actions is None:
            return None
        actions = [ResolutionToolAction.model_validate(item) for item in raw_actions]
        return cls({(action.step, action.candidate_ref): action for action in actions})

    def for_ref(
        self,
        step: ResolutionStep,
        candidate_ref: str,
    ) -> ResolutionToolAction | None:
        return self.actions.get((step, candidate_ref))

    @staticmethod
    def is_skip(action: ResolutionToolAction | None) -> bool:
        return action is not None and action.tool_name in {
            ResolutionToolName.DEFER_OR_IGNORE,
        }

    @staticmethod
    def is_update(action: ResolutionToolAction | None) -> bool:
        return action is not None and action.tool_name in {
            ResolutionToolName.UPDATE_MEMORY,
            ResolutionToolName.UPDATE_RELATIONSHIP,
        }

    @staticmethod
    def node_update(write: GraphNodeWrite, action: ResolutionToolAction) -> GraphNodeWrite:
        return write.model_copy(update={"target_ref": action.target_ref}, deep=True)

    @staticmethod
    def apply_node_payload(
        write: GraphNodeWrite,
        action: ResolutionToolAction,
    ) -> GraphNodeWrite:
        """Apply the model's validated structured identity patch to a node write."""

        if action.tool_name not in {
            ResolutionToolName.CREATE_NODE,
            ResolutionToolName.UPDATE_NODE,
        }:
            return write
        properties = dict(write.properties)
        display_name = action.payload.get("display_name")
        if isinstance(display_name, str) and display_name.strip():
            if write.label == "Person":
                name_field = "display_name"
            elif write.label == "Event":
                name_field = "title"
            else:
                name_field = "name"
            properties[name_field] = display_name.strip()
            if write.label in NORMALIZED_NAME_LABELS:
                properties["normalized_name"] = normalize_text(display_name)
        aliases = action.payload.get("aliases")
        if aliases:
            properties["aliases"] = list(aliases)
        return write.model_copy(update={"properties": properties}, deep=True)

    @staticmethod
    def relationship_endpoints(
        write: GraphRelationshipWrite,
        action: ResolutionToolAction,
    ) -> GraphRelationshipWrite:
        updates: dict[str, Any] = {}
        if action.from_ref is not None:
            updates["from_ref"] = action.from_ref
        if action.to_ref is not None:
            updates["to_ref"] = action.to_ref
        return write.model_copy(update=updates, deep=True)
