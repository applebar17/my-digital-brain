"""Backend interpretation of validated resolution actions for write planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from my_digital_brain.ingestion.contracts import (
    GraphNodeWrite,
    GraphRelationshipWrite,
    ResolutionStep,
    ResolutionToolAction,
    ResolutionToolName,
    ResolutionResult,
)


@dataclass(frozen=True, slots=True)
class ResolutionWriteActions:
    """Validated action index; an absent index preserves pre-Wave-5 behavior."""

    actions: dict[tuple[ResolutionStep, str], ResolutionToolAction]

    @classmethod
    def from_result(cls, result: ResolutionResult) -> "ResolutionWriteActions | None":
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
            ResolutionToolName.ASK_CLARIFICATION,
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
