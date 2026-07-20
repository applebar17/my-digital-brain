"""Pure helpers shared by the reasoning-first ingestion runtime."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    CandidateOutput,
    ClarificationRequest,
    ClarificationRequestDraft,
    EntityIngestionPlanDraft,
    ExtractionPlan,
    ExtractionTask,
    GraphContextPack,
    IngestionContextPackage,
    IngestionResult,
    MemoryLogIngestionPlanDraft,
    SourceRecordRef,
    ValidationIssue,
)
from my_digital_brain.ingestion.enums import ExtractionExecutionMode, ExtractionTaskType, IngestionStatus
from my_digital_brain.ingestion.ontology import ontology_prompt_payload, task_type_for_entity_type

DEFAULT_EXTRACTION_DRAFT_BATCH_SIZE = 3
MAX_EXTRACTION_DRAFT_BATCH_SIZE = 10


def entity_extraction_plan(
    source: SourceRecordRef,
    graph_context_pack: GraphContextPack,
    entity_plan: EntityIngestionPlanDraft,
) -> ExtractionPlan:
    tasks: list[ExtractionTask] = []
    issues: list[str] = []
    for action_index, action in enumerate(entity_plan.actions, start=1):
        action_payload = action.model_dump(mode="json", exclude_none=True)
        for entity_index, entity in enumerate(action.entities, start=1):
            if entity.suggested_entity_type is None:
                issues.append(entity.local_ref)
                continue
            task_type = task_type_for_entity_type(entity.suggested_entity_type)
            tasks.append(
                ExtractionTask(
                    task_type=task_type,
                    target_ref=entity.local_ref,
                    evidence_text=entity.evidence_text,
                    source_refs=[source.source_id],
                    expected_output=(
                        "Extract exactly one entity candidate using task.target_ref "
                        "as the candidate local_ref."
                    ),
                    required_context_refs=list(entity.context_refs),
                    notes=entity.notes or action.goal,
                    metadata={
                        "schema_layer": "reasoning_first_entity_extraction",
                        "entity_action_goal": action.goal,
                        "entity_action_index": action_index,
                        "planned_entity_index": entity_index,
                        "planned_entity": entity.model_dump(mode="json", exclude_none=True),
                        "planning_action": action_payload,
                        "suggested_entity_type": str(entity.suggested_entity_type),
                        "aliases": list(entity.aliases),
                        "allowed_local_refs": [entity.local_ref],
                        "ontology": ontology_prompt_payload(),
                    },
                ),
            )
    return ExtractionPlan(
        source_id=source.source_id,
        context_package_id=graph_context_pack.context_pack_id,
        execution_mode=ExtractionExecutionMode.FOCUSED_EXTRACTION,
        reason=entity_plan.reason,
        tasks=tasks,
        clarification=(clarification_from_draft(entity_plan.clarification) if entity_plan.clarification else None),
        context_gaps=list(entity_plan.context_gaps),
        metadata={
            "schema_layer": "reasoning_first_entity_extraction_plan",
            "skipped_actions_missing_entity_type": issues,
        },
    )


def memory_log_extraction_plan(
    source: SourceRecordRef,
    graph_context_pack: GraphContextPack,
    memory_log_plan: MemoryLogIngestionPlanDraft,
) -> ExtractionPlan:
    tasks: list[ExtractionTask] = []
    for action_index, action in enumerate(memory_log_plan.actions, start=1):
        action_payload = action.model_dump(mode="json", exclude_none=True)
        for memory_log_index, memory_log in enumerate(action.memory_logs, start=1):
            tasks.append(
                ExtractionTask(
                    task_type=ExtractionTaskType.MEMORY_LOG,
                    target_ref=memory_log.local_ref,
                    evidence_text=memory_log.evidence_text,
                    source_refs=[source.source_id],
                    expected_output=(
                        "Extract exactly one MemoryLog draft using task.target_ref "
                        "as the MemoryLog local_ref."
                    ),
                    required_context_refs=[
                        *list(memory_log.host_refs),
                        *list(memory_log.involved_refs),
                        *list(memory_log.relationship_context_refs),
                    ],
                    notes=memory_log.notes or action.goal,
                    metadata={
                        "schema_layer": "reasoning_first_memory_log_extraction",
                        "memory_log_action_goal": action.goal,
                        "memory_log_action_index": action_index,
                        "planned_memory_log_index": memory_log_index,
                        "planned_memory_log": memory_log.model_dump(mode="json", exclude_none=True),
                        "memory_log_planning_action": action_payload,
                        "allowed_local_refs": [memory_log.local_ref],
                    },
                ),
            )
    return ExtractionPlan(
        source_id=source.source_id,
        context_package_id=graph_context_pack.context_pack_id,
        execution_mode=ExtractionExecutionMode.FOCUSED_EXTRACTION,
        reason=memory_log_plan.reason,
        tasks=tasks,
        clarification=(clarification_from_draft(memory_log_plan.clarification) if memory_log_plan.clarification else None),
        context_gaps=list(memory_log_plan.context_gaps),
        metadata={"schema_layer": "reasoning_first_memory_log_extraction_plan"},
    )


def predefined_entity_extraction_plan(source: SourceRecordRef, graph_context_pack: GraphContextPack) -> ExtractionPlan:
    return ExtractionPlan(
        source_id=source.source_id,
        context_package_id=graph_context_pack.context_pack_id,
        execution_mode=ExtractionExecutionMode.FOCUSED_EXTRACTION,
        reason="Predefined entity candidates supplied by a local UAT fixture.",
        tasks=[],
        metadata={"schema_layer": "reasoning_first_predefined_entity_candidates"},
    )


def combined_extraction_plan(
    source: SourceRecordRef,
    graph_context_pack: GraphContextPack,
    plans: Sequence[ExtractionPlan],
) -> ExtractionPlan:
    tasks: list[ExtractionTask] = []
    context_gaps: list[str] = []
    plan_refs: list[str] = []
    reasons: list[str] = []
    for plan in plans:
        plan_refs.append(plan.extraction_plan_id)
        tasks.extend(plan.tasks)
        context_gaps.extend(plan.context_gaps)
        if plan.reason:
            reasons.append(plan.reason)
    return ExtractionPlan(
        source_id=source.source_id,
        context_package_id=graph_context_pack.context_pack_id,
        execution_mode=ExtractionExecutionMode.FOCUSED_EXTRACTION,
        reason="; ".join(reasons) or "Reasoning-first ingestion candidate preparation.",
        tasks=tasks,
        context_gaps=context_gaps,
        metadata={
            "schema_layer": "reasoning_first_candidate_graph_combined_plan",
            "component_extraction_plan_ids": plan_refs,
        },
    )


def ensure_candidate_source_ref(candidate: CandidateEntity, source: SourceRecordRef) -> CandidateEntity:
    if candidate.source_refs or candidate.evidence_refs:
        return candidate
    return candidate.model_copy(update={"source_refs": [source.source_id]})


def context_package_for_services(source: SourceRecordRef, graph_context_pack: GraphContextPack) -> IngestionContextPackage:
    """Adapt the compact graph packet to the service contract used by extractors and writes."""
    return IngestionContextPackage(
        source_id=source.source_id,
        aliases=dict(graph_context_pack.alias_map),
        reference_registry_snapshot=dict(graph_context_pack.reference_registry_snapshot),
        identity_lookup_packets=list(graph_context_pack.identity_lookup_packets),
        entities=[entity.model_dump(mode="json", exclude_none=True) for entity in graph_context_pack.entities],
        relationships=[relationship.model_dump(mode="json", exclude_none=True) for relationship in graph_context_pack.relationships],
        notes=list(graph_context_pack.notes),
        metadata={
            "graph_context_pack_id": graph_context_pack.context_pack_id,
            "retrieval_strategy": graph_context_pack.retrieval_strategy,
        },
        owner_snapshot=graph_context_pack.owner_snapshot,
    )


def batch_extraction_items(
    items: Sequence[tuple[int, ExtractionTask, Any]],
    batch_size: int,
) -> list[list[tuple[int, ExtractionTask, Any]]]:
    batches: list[list[tuple[int, ExtractionTask, Any]]] = []
    current: list[tuple[int, ExtractionTask, Any]] = []
    current_extractor: Any | None = None
    for item in items:
        extractor = item[2]
        if current and extractor is not current_extractor:
            batches.extend(batch_sequence(current, batch_size))
            current = []
        current.append(item)
        current_extractor = extractor
    if current:
        batches.extend(batch_sequence(current, batch_size))
    return batches


def extract_with_optional_batch(extractor: Any, source: SourceRecordRef, tasks: Sequence[ExtractionTask], context: IngestionContextPackage) -> Sequence[CandidateOutput]:
    if not tasks:
        return []
    extract_batch = getattr(extractor, "extract_batch", None)
    if callable(extract_batch) and len(tasks) > 1:
        return extract_batch(source, tasks, context)
    candidates: list[CandidateOutput] = []
    for task in tasks:
        candidates.extend(extractor.extract(source, task, context))
    return candidates


def batch_sequence(items: Sequence[Any], batch_size: int) -> list[list[Any]]:
    normalized_size = normalized_extraction_batch_size(batch_size)
    batches = [list(items[index : index + normalized_size]) for index in range(0, len(items), normalized_size)]
    if len(batches) > 1 and len(batches[-1]) == 1 and len(batches[-2]) < MAX_EXTRACTION_DRAFT_BATCH_SIZE:
        batches[-2].extend(batches.pop())
    return batches


def normalized_extraction_batch_size(value: int) -> int:
    try:
        batch_size = int(value)
    except (TypeError, ValueError):
        batch_size = DEFAULT_EXTRACTION_DRAFT_BATCH_SIZE
    return max(1, min(batch_size, MAX_EXTRACTION_DRAFT_BATCH_SIZE))


def clarification_from_draft(draft: ClarificationRequestDraft | None) -> ClarificationRequest | None:
    if draft is None:
        return None
    return ClarificationRequest(
        doubt=draft.doubt,
        reason=draft.reason,
        target_refs=list(draft.target_refs),
        options=draft.options,
        blocking=draft.blocking,
        metadata={"schema_layer": "reasoning_first_ingestion"},
    )


def clarification_from_agentic_result(result: Any) -> ClarificationRequest | None:
    if getattr(result, "status", None) != "interrupted":
        return None
    interruption = result.metadata.get("interruption", {}) if result.metadata else {}
    packet = interruption.get("clarification_packet") or {}
    questions = packet.get("questions") or []
    first_question = questions[0] if questions else {}
    option_labels = [str(option.get("label") or "").strip() for option in first_question.get("options", []) if str(option.get("label") or "").strip()]
    doubt = str(first_question.get("question") or "").strip() or result.assistant_text or "Clarification is required before ingestion can continue."
    reason = str(packet.get("reason") or "").strip() or str(interruption.get("reason") or "").strip() or "The agentic ingestion step requested clarification."
    return ClarificationRequest(
        doubt=doubt,
        reason=reason,
        target_refs=list(packet.get("target_refs") or interruption.get("target_refs") or []),
        options="; ".join(option_labels) if option_labels else None,
        blocking=True,
        metadata={"schema_layer": "reasoning_first_ingestion", "agentic_interruption": interruption},
    )


def structured_step_failure(source: SourceRecordRef, stage: str, message: str) -> IngestionResult:
    return IngestionResult(
        source_id=source.source_id,
        status=IngestionStatus.VALIDATION_FAILED,
        validation_errors=[ValidationIssue(field_path=stage, message=message, code=f"ingestion_{stage}_failed")],
        metadata={"ingestion_stage": stage},
    )


def timezone_for_source(source: SourceRecordRef) -> str:
    return str(source.metadata.get("timezone") or "UTC")


def write_plan_has_mutations(write_plan: Any) -> bool:
    return any((write_plan.nodes_to_create, write_plan.nodes_to_update, write_plan.relationships_to_create, write_plan.relationships_to_update, write_plan.claims_to_create, write_plan.perceptions_to_create, write_plan.relationship_contexts_to_create, write_plan.memory_logs_to_create, write_plan.metadata_patches))


def write_plan_counts(write_plan: Any) -> dict[str, int]:
    return {
        "nodes_to_create": len(write_plan.nodes_to_create),
        "nodes_to_update": len(write_plan.nodes_to_update),
        "relationships_to_create": len(write_plan.relationships_to_create),
        "relationships_to_update": len(write_plan.relationships_to_update),
        "claims_to_create": len(write_plan.claims_to_create),
        "perceptions_to_create": len(write_plan.perceptions_to_create),
        "relationship_contexts_to_create": len(write_plan.relationship_contexts_to_create),
        "memory_logs_to_create": len(write_plan.memory_logs_to_create),
        "metadata_patches": len(write_plan.metadata_patches),
    }


def validation_issue_summaries(issues: Sequence[ValidationIssue], *, limit: int = 20) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for issue in issues[:limit]:
        summaries.append({key: value for key, value in {"code": issue.code, "field_path": issue.field_path, "message": short_text(issue.message), "details": compact_issue_details(issue.details)}.items() if value not in (None, "", {}, [])})
    if len(issues) > limit:
        summaries.append({"code": "truncated", "remaining_count": len(issues) - limit})
    return summaries


def compact_issue_details(details: dict[str, object]) -> dict[str, object]:
    allowed_keys = {"label", "relationship_type", "ref", "count", "execution_mode", "task_id", "task_type", "candidate_count"}
    return {key: short_text(value) if isinstance(value, str) else value for key, value in details.items() if key in allowed_keys}


def short_text(value: str, *, max_chars: int = 260) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}..."
