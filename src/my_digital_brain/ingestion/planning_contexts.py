from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from my_digital_brain.agentic import ConversationContext, PlanningTransformContext
from my_digital_brain.ingestion.contracts import (
    EntityIngestionPlanDraft,
    GraphContextPackView,
    IngestionReasoningCheckpointDraft,
    MissingEntityRequiredDraft,
    RelationshipIngestionPlanDraft,
    ResolvedEntityMap,
)
from my_digital_brain.ingestion.planning_guidelines import (
    entity_ingestion_planning_guidelines,
    missing_entity_planning_guidelines,
    relationship_ingestion_planning_guidelines,
)


def build_entity_planning_context(
    *,
    source_text: str,
    graph_context_view: GraphContextPackView,
    reasoning: IngestionReasoningCheckpointDraft,
    conversation: ConversationContext | None = None,
    current_time: datetime | None = None,
    timezone: str = "UTC",
) -> PlanningTransformContext:
    payload: dict[str, Any] = {
        "planning_scope": "entities_only",
        "source_text": source_text,
        "graph_context_view": _dump(graph_context_view),
        "rules": [
            "Plan entity preparation only.",
            "Aliases are hints, not identity or automatic node fields.",
            "Do not plan relationship candidates.",
        ],
    }
    return _planning_context(
        purpose=entity_ingestion_planning_guidelines(),
        input_context=payload,
        reasoning=reasoning,
        conversation=conversation,
        current_time=current_time,
        timezone=timezone,
        expected_output_schema=EntityIngestionPlanDraft.__name__,
    )


def build_relationship_planning_context(
    *,
    source_text: str,
    graph_context_view: GraphContextPackView,
    reasoning: IngestionReasoningCheckpointDraft,
    resolved_entity_map: ResolvedEntityMap,
    conversation: ConversationContext | None = None,
    current_time: datetime | None = None,
    timezone: str = "UTC",
) -> PlanningTransformContext:
    payload: dict[str, Any] = {
        "planning_scope": "relationships_only",
        "source_text": source_text,
        "graph_context_view": _dump(graph_context_view),
        "resolved_entity_map_view": _resolved_entity_map_view(resolved_entity_map),
        "rules": [
            "Plan relationships only against relationship-usable refs.",
            "Emit missing entity requirements instead of inventing endpoints.",
            "Do not plan new entity creation in this step.",
        ],
    }
    return _planning_context(
        purpose=relationship_ingestion_planning_guidelines(),
        input_context=payload,
        reasoning=reasoning,
        conversation=conversation,
        current_time=current_time,
        timezone=timezone,
        expected_output_schema=RelationshipIngestionPlanDraft.__name__,
    )


def build_missing_entity_planning_context(
    *,
    source_text: str,
    graph_context_view: GraphContextPackView,
    reasoning: IngestionReasoningCheckpointDraft,
    missing_entity: MissingEntityRequiredDraft,
    resolved_entity_map: ResolvedEntityMap | None = None,
    conversation: ConversationContext | None = None,
    current_time: datetime | None = None,
    timezone: str = "UTC",
) -> PlanningTransformContext:
    payload: dict[str, Any] = {
        "planning_scope": "missing_entity_only",
        "source_text": source_text,
        "graph_context_view": _dump(graph_context_view),
        "missing_entity_required": _dump(missing_entity),
        "rules": [
            "Plan only the missing endpoint.",
            "Keep relationship resume guidance available for the later relationship pass.",
            "Do not plan unrelated entities or complete the relationship here.",
        ],
    }
    if resolved_entity_map is not None:
        payload["resolved_entity_map_view"] = _resolved_entity_map_view(
            resolved_entity_map,
        )
    return _planning_context(
        purpose=missing_entity_planning_guidelines(),
        input_context=payload,
        reasoning=reasoning,
        conversation=conversation,
        current_time=current_time,
        timezone=timezone,
        expected_output_schema=EntityIngestionPlanDraft.__name__,
    )


def _planning_context(
    *,
    purpose,
    input_context: dict[str, Any],
    reasoning: IngestionReasoningCheckpointDraft,
    conversation: ConversationContext | None,
    current_time: datetime | None,
    timezone: str,
    expected_output_schema: str,
) -> PlanningTransformContext:
    values: dict[str, Any] = {
        "purpose": purpose,
        "input_context": input_context,
        "reasoning_artifact": _dump(reasoning),
        "conversation": conversation,
        "timezone": timezone,
        "expected_output_schema": expected_output_schema,
    }
    if current_time is not None:
        values["current_time"] = current_time
    return PlanningTransformContext(**values)


def _resolved_entity_map_view(resolved_entity_map: ResolvedEntityMap) -> dict[str, Any]:
    return {
        "relationship_usable_refs": resolved_entity_map.relationship_usable_refs,
        "entries": [
            {
                "local_ref": entry.local_ref,
                "relationship_ref": entry.relationship_ref,
                "status": entry.status,
                "display_label": entry.display_label,
                "entity_type": entry.entity_type,
                "duplicate_notes": entry.duplicate_notes,
                "ambiguity_notes": entry.ambiguity_notes,
            }
            for entry in resolved_entity_map.entries
        ],
        "notes": list(resolved_entity_map.notes),
    }


def _dump(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    return value
