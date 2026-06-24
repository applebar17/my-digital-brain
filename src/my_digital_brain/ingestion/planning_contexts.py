from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from my_digital_brain.agentic import ConversationContext, PlanningTransformContext
from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    EntityIngestionPlanDraft,
    GraphContextPackView,
    IngestionReasoningCheckpointDraft,
    MemoryLog,
    MemoryLogDraftBatch,
    MemoryLogIngestionActionDraft,
    MemoryLogIngestionPlanDraft,
    MissingEntityRequiredDraft,
    PlannedMemoryLogRefDraft,
    RelationshipIngestionPlanDraft,
    ResolvedEntityMap,
)
from my_digital_brain.ingestion.planning_guidelines import (
    entity_ingestion_planning_guidelines,
    memory_log_ingestion_planning_guidelines,
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
            "Create candidate local_refs in the current CANDIDATE_* naming style.",
            "Each planned entity target must keep its local_ref through extraction and later planning.",
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
    entity_packet: list[dict[str, Any]] | None = None,
    memory_log_packet: list[dict[str, Any]] | None = None,
    conversation: ConversationContext | None = None,
    current_time: datetime | None = None,
    timezone: str = "UTC",
) -> PlanningTransformContext:
    payload: dict[str, Any] = {
        "planning_scope": "relationships_only",
        "source_text": source_text,
        "graph_context_view": _dump(graph_context_view),
        "resolved_entity_map_view": _resolved_entity_map_view(resolved_entity_map),
        "entity_packet": entity_packet or [],
        "memory_log_packet": memory_log_packet or [],
        "rules": [
            "Plan relationships only against relationship-usable refs.",
            "Create candidate local_refs for relationship outputs in the current CANDIDATE_* naming style.",
            "Use memory-log refs as episodic context, not as substitutes for durable relationship endpoints.",
            "Keep weak co-presence as MemoryLog involvement unless the source states a durable relationship.",
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


def build_memory_log_planning_context(
    *,
    source_text: str,
    graph_context_view: GraphContextPackView,
    reasoning: IngestionReasoningCheckpointDraft,
    resolved_entity_map: ResolvedEntityMap,
    entity_packet: list[dict[str, Any]],
    conversation: ConversationContext | None = None,
    current_time: datetime | None = None,
    timezone: str = "UTC",
) -> PlanningTransformContext:
    payload: dict[str, Any] = {
        "planning_scope": "memory_logs_only",
        "source_text": source_text,
        "graph_context_view": _dump(graph_context_view),
        "resolved_entity_map_view": _resolved_entity_map_view(resolved_entity_map),
        "entity_packet": entity_packet,
        "rules": [
            "Plan compact MemoryLog records only.",
            "Create MEMORY_LOG_* local_refs and keep them stable through extraction.",
            "Use only refs from entity_packet, resolved_entity_map_view, or graph_context_view.",
            "Every planned MemoryLog needs at least one host_ref.",
            "Use involved_refs for weak co-presence instead of planning durable edges.",
            "Do not plan relationship candidates in this step.",
        ],
    }
    return _planning_context(
        purpose=memory_log_ingestion_planning_guidelines(),
        input_context=payload,
        reasoning=reasoning,
        conversation=conversation,
        current_time=current_time,
        timezone=timezone,
        expected_output_schema=MemoryLogIngestionPlanDraft.__name__,
    )


def build_memory_log_extraction_context(
    *,
    source_text: str,
    graph_context_view: GraphContextPackView,
    reasoning: IngestionReasoningCheckpointDraft,
    resolved_entity_map: ResolvedEntityMap,
    entity_packet: list[dict[str, Any]],
    memory_log_plan: MemoryLogIngestionPlanDraft,
    planning_action: MemoryLogIngestionActionDraft,
    planned_memory_log: PlannedMemoryLogRefDraft,
    memory_log_index: int,
    conversation: ConversationContext | None = None,
    current_time: datetime | None = None,
    timezone: str = "UTC",
) -> PlanningTransformContext:
    payload: dict[str, Any] = {
        "planning_scope": "memory_log_extraction",
        "source_text": source_text,
        "graph_context_view": _dump(graph_context_view),
        "resolved_entity_map_view": _resolved_entity_map_view(resolved_entity_map),
        "entity_packet": entity_packet,
        "memory_log_plan": memory_log_plan.model_dump(mode="json", exclude_none=True),
        "planning_action": planning_action.model_dump(mode="json", exclude_none=True),
        "planned_memory_log": planned_memory_log.model_dump(mode="json", exclude_none=True),
        "expected_local_ref": planned_memory_log.local_ref,
        "memory_log_index": memory_log_index,
        "rules": [
            "Extract exactly one MemoryLog draft for the planned memory-log target.",
            "Use expected_local_ref exactly as the MemoryLog local_ref.",
            "Use host_refs and involved_refs from the planning target unless source context disproves them.",
            "Preserve provenance, evidence, original user wording, and temporal hints.",
            "Do not create relationship candidates or graph writes in this step.",
        ],
    }
    return _planning_context(
        purpose=memory_log_ingestion_planning_guidelines().model_copy(
            update={
                "purpose_id": "memory_log_ingestion_extraction",
                "goal": "Extract a backend-facing MemoryLog draft from one planned memory-log target.",
                "output_usage": MemoryLogDraftBatch.__name__,
            },
        ),
        input_context=payload,
        reasoning=reasoning,
        conversation=conversation,
        current_time=current_time,
        timezone=timezone,
        expected_output_schema=MemoryLogDraftBatch.__name__,
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
            "Create exactly the candidate local_ref needed for the missing endpoint.",
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


def build_resolved_entity_packet(
    entities: list[CandidateEntity],
    resolved_entity_map: ResolvedEntityMap,
) -> list[dict[str, Any]]:
    packet: list[dict[str, Any]] = []
    for entity in entities:
        entry = resolved_entity_map.entry_for(entity.local_ref)
        packet.append(
            {
                key: value
                for key, value in {
                    "local_ref": entity.local_ref,
                    "entity_type": entity.entity_type,
                    "display_name": entity.display_name,
                    "relationship_ref": (
                        entry.relationship_ref if entry is not None else None
                    ),
                    "status": entry.status if entry is not None else None,
                    "graph_alias": entry.graph_alias if entry is not None else None,
                    "aliases": list(entity.aliases),
                }.items()
                if value not in (None, [], {})
            },
        )
    return packet


def build_memory_log_packet(memory_logs: list[MemoryLog]) -> list[dict[str, Any]]:
    packet: list[dict[str, Any]] = []
    for memory_log in memory_logs:
        packet.append(
            {
                key: value
                for key, value in {
                    "local_ref": memory_log.local_ref,
                    "log_text": memory_log.log_text,
                    "host_refs": list(memory_log.host_target_ids),
                    "involved_refs": list(memory_log.involved_target_ids),
                    "relationship_context_refs": [
                        link.target_id
                        for link in memory_log.links
                        if link.relationship_type == "UPDATES_RELATIONSHIP"
                    ],
                    "happened_at": memory_log.happened_at,
                    "source_kind": str(memory_log.source_kind),
                    "importance": str(memory_log.importance),
                }.items()
                if value not in (None, [], {})
            },
        )
    return packet


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
