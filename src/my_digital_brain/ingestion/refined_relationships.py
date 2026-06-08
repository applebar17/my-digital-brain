from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from my_digital_brain.ingestion.contracts import (
    CandidateClaim,
    CandidateMetadataPatch,
    CandidateOutput,
    CandidatePerception,
    CandidateRelationship,
    CandidateRelationshipContext,
    ExtractionPlan,
    ExtractionTask,
    GraphContextPack,
    RelationshipIngestionPlanDraft,
    ResolvedEntityMap,
    SourceRecordRef,
    ValidationIssue,
)
from my_digital_brain.ingestion.enums import ExtractionExecutionMode, ExtractionTaskType
from my_digital_brain.ingestion.ontology import ontology_prompt_payload


@dataclass(slots=True)
class RelationshipExtractionPlanBuildResult:
    extraction_plan: ExtractionPlan
    validation_issues: list[ValidationIssue]
    blocked_action_refs: list[str]


def build_relationship_extraction_plan(
    source: SourceRecordRef,
    graph_context_pack: GraphContextPack,
    relationship_plan: RelationshipIngestionPlanDraft,
    resolved_entity_map: ResolvedEntityMap,
) -> RelationshipExtractionPlanBuildResult:
    tasks: list[ExtractionTask] = []
    issues: list[ValidationIssue] = []
    skipped_deferred: list[str] = []
    blocked_action_refs: list[str] = []
    graph_aliases = _known_graph_aliases(graph_context_pack)
    missing_refs = {item.missing_ref for item in relationship_plan.missing_entities}

    for index, action in enumerate(relationship_plan.actions, start=1):
        if action.storage_shape == "defer":
            skipped_deferred.append(action.action_ref)
            continue
        if _action_depends_on_missing_ref(action.depends_on, missing_refs):
            blocked_action_refs.append(action.action_ref)
            continue

        from_ref, from_issue = _relationship_endpoint_ref(
            action.from_ref,
            field_path=f"relationship_plan.actions[{index - 1}].from_ref",
            resolved_entity_map=resolved_entity_map,
            graph_aliases=graph_aliases,
            missing_refs=missing_refs,
        )
        to_ref, to_issue = _relationship_endpoint_ref(
            action.to_ref,
            field_path=f"relationship_plan.actions[{index - 1}].to_ref",
            resolved_entity_map=resolved_entity_map,
            graph_aliases=graph_aliases,
            missing_refs=missing_refs,
        )
        if from_issue is not None:
            if from_issue.code == "blocked_by_missing_entity":
                blocked_action_refs.append(action.action_ref)
            else:
                issues.append(from_issue)
        if to_issue is not None:
            if to_issue.code == "blocked_by_missing_entity":
                blocked_action_refs.append(action.action_ref)
            else:
                issues.append(to_issue)
        if from_ref is None or to_ref is None:
            continue

        task_type = _task_type_for_storage_shape(action.storage_shape)
        if task_type is None:
            issues.append(
                _issue(
                    f"relationship_plan.actions[{index - 1}].storage_shape",
                    f"Unsupported relationship storage shape '{action.storage_shape}'.",
                    "unsupported_relationship_storage_shape",
                    {"storage_shape": str(action.storage_shape)},
                ),
            )
            continue

        tasks.append(
            ExtractionTask(
                task_type=task_type,
                target_ref=action.action_ref,
                evidence_text=action.evidence_text,
                source_refs=[source.source_id],
                expected_output=_expected_output_for_task(task_type),
                required_context_refs=[from_ref, to_ref],
                notes=action.notes or action.relationship_intent or action.goal,
                metadata={
                    "schema_layer": "refined_relationship_extraction",
                    "relationship_action_ref": action.action_ref,
                    "relationship_action_goal": action.goal,
                    "relationship_action_index": index,
                    "relationship_intent": action.relationship_intent,
                    "storage_shape": str(action.storage_shape),
                    "original_from_ref": action.from_ref,
                    "original_to_ref": action.to_ref,
                    "resolved_from_ref": from_ref,
                    "resolved_to_ref": to_ref,
                    "relationship_depends_on": list(action.depends_on),
                    "ontology": ontology_prompt_payload(),
                },
            ),
        )

    return RelationshipExtractionPlanBuildResult(
        extraction_plan=ExtractionPlan(
            source_id=source.source_id,
            context_package_id=graph_context_pack.context_pack_id,
            execution_mode=ExtractionExecutionMode.FOCUSED_EXTRACTION,
            reason=relationship_plan.reason,
            tasks=tasks,
            clarification=None,
            context_gaps=list(relationship_plan.context_gaps),
            metadata={
                "schema_layer": "refined_relationship_extraction_plan",
                "blocked_action_refs": sorted(set(blocked_action_refs)),
                "skipped_deferred_actions": skipped_deferred,
                "missing_entity_refs": sorted(missing_refs),
            },
        ),
        validation_issues=issues,
        blocked_action_refs=sorted(set(blocked_action_refs)),
    )


def normalize_relationship_candidate_refs(
    candidates: list[CandidateOutput],
    resolved_entity_map: ResolvedEntityMap,
) -> list[CandidateOutput]:
    return [
        _normalize_candidate_refs(candidate, resolved_entity_map)
        for candidate in candidates
    ]


def _relationship_endpoint_ref(
    ref: str | None,
    *,
    field_path: str,
    resolved_entity_map: ResolvedEntityMap,
    graph_aliases: set[str],
    missing_refs: set[str],
) -> tuple[str | None, ValidationIssue | None]:
    if ref is None or not ref.strip():
        return None, _issue(
            field_path,
            "Relationship action endpoint is missing.",
            "missing_relationship_endpoint",
        )
    ref = ref.strip()
    if ref in missing_refs or ref.startswith("MISSING_"):
        return None, _issue(
            field_path,
            f"Relationship endpoint '{ref}' is blocked by a missing entity.",
            "blocked_by_missing_entity",
            {"ref": ref},
        )

    relationship_ref = resolved_entity_map.relationship_ref_for(ref)
    if relationship_ref is not None:
        return relationship_ref, None

    entry = resolved_entity_map.entry_for(ref)
    if entry is not None:
        return None, _issue(
            field_path,
            f"Resolved entity ref '{ref}' is not usable for relationships.",
            "relationship_unusable_resolved_ref",
            {"ref": ref, "status": str(entry.status)},
        )

    if ref in resolved_entity_map.relationship_usable_refs.values():
        return ref, None
    if ref in graph_aliases:
        return ref, None
    if ref.startswith("CANDIDATE_"):
        return None, _issue(
            field_path,
            f"Unknown candidate endpoint '{ref}'.",
            "unknown_candidate_relationship_endpoint",
            {"ref": ref, "known_refs": sorted(resolved_entity_map.relationship_usable_refs)},
        )
    if _looks_like_planner_ref(ref):
        return None, _issue(
            field_path,
            f"Planner action ref '{ref}' cannot be used as a relationship endpoint.",
            "planner_ref_relationship_endpoint",
            {"ref": ref},
        )
    return None, _issue(
        field_path,
        (
            f"Unknown relationship endpoint '{ref}'. Use a resolved local ref or "
            "a graph alias from rendered context."
        ),
        "unknown_relationship_endpoint",
        {"ref": ref, "known_graph_aliases": sorted(graph_aliases)},
    )


def _task_type_for_storage_shape(storage_shape: str) -> ExtractionTaskType | None:
    if storage_shape == "direct_relationship":
        return ExtractionTaskType.RELATIONSHIP
    if storage_shape == "relationship_context":
        return ExtractionTaskType.RELATIONSHIP_CONTEXT
    if storage_shape == "perception":
        return ExtractionTaskType.PERCEPTION
    if storage_shape == "claim":
        return ExtractionTaskType.CLAIM
    if storage_shape == "metadata_note":
        return ExtractionTaskType.METADATA_PATCH
    return None


def _expected_output_for_task(task_type: ExtractionTaskType) -> str:
    if task_type == ExtractionTaskType.RELATIONSHIP:
        return "Extract relationship candidates only, using the resolved endpoint refs."
    if task_type == ExtractionTaskType.RELATIONSHIP_CONTEXT:
        return "Extract relationship context candidates only, using the resolved endpoint refs."
    if task_type == ExtractionTaskType.PERCEPTION:
        return "Extract perception candidates only for the resolved target refs."
    if task_type == ExtractionTaskType.CLAIM:
        return "Extract claim candidates only for the resolved about refs."
    if task_type == ExtractionTaskType.METADATA_PATCH:
        return "Extract metadata patch candidates only for the resolved target refs."
    return "Extract candidates only for the focused relationship action."


def _known_graph_aliases(pack: GraphContextPack) -> set[str]:
    aliases = {"OWNER"}
    aliases.update(item.ref for item in pack.entities)
    aliases.update(item.target_ref for item in pack.known_aliases if item.target_ref)
    for relationship in pack.relationships:
        aliases.add(relationship.from_ref)
        aliases.add(relationship.to_ref)
    for snippet in pack.relationship_context_snippets:
        aliases.update(snippet.endpoint_refs)
    return {alias for alias in aliases if alias}


def _action_depends_on_missing_ref(depends_on: list[str], missing_refs: set[str]) -> bool:
    return any(ref in missing_refs or ref.startswith("MISSING_") for ref in depends_on)


def _looks_like_planner_ref(ref: str) -> bool:
    return ref.startswith(("ENTITY_ACTION_", "REL_ACTION_", "ACTION_"))


def _normalize_candidate_refs(
    candidate: CandidateOutput,
    resolved_entity_map: ResolvedEntityMap,
) -> CandidateOutput:
    if isinstance(candidate, CandidateRelationship):
        return _copy_with_refs(
            candidate,
            resolved_entity_map,
            {"from_ref": candidate.from_ref, "to_ref": candidate.to_ref},
        )
    if isinstance(candidate, CandidateRelationshipContext):
        return _copy_with_refs(
            candidate,
            resolved_entity_map,
            {"from_ref": candidate.from_ref, "to_ref": candidate.to_ref},
        )
    if isinstance(candidate, CandidatePerception):
        return _copy_with_refs(
            candidate,
            resolved_entity_map,
            {"target_ref": candidate.target_ref},
        )
    if isinstance(candidate, CandidateClaim):
        refs = [_resolved_or_original(ref, resolved_entity_map) for ref in candidate.about_refs]
        if refs == candidate.about_refs:
            return candidate
        return candidate.model_copy(
            update={
                "about_refs": refs,
                "metadata": _normalization_metadata(
                    candidate.metadata,
                    {"about_refs": candidate.about_refs},
                    {"about_refs": refs},
                ),
            },
        )
    if isinstance(candidate, CandidateMetadataPatch):
        return _copy_with_refs(
            candidate,
            resolved_entity_map,
            {"target_ref": candidate.target_ref},
        )
    return candidate


def _copy_with_refs(
    candidate: CandidateOutput,
    resolved_entity_map: ResolvedEntityMap,
    refs: dict[str, str],
) -> CandidateOutput:
    normalized = {
        field_name: _resolved_or_original(ref, resolved_entity_map)
        for field_name, ref in refs.items()
    }
    if normalized == refs:
        return candidate
    return candidate.model_copy(
        update={
            **normalized,
            "metadata": _normalization_metadata(candidate.metadata, refs, normalized),
        },
    )


def _resolved_or_original(ref: str, resolved_entity_map: ResolvedEntityMap) -> str:
    return resolved_entity_map.relationship_ref_for(ref) or ref


def _normalization_metadata(
    metadata: dict[str, Any],
    original: dict[str, Any],
    normalized: dict[str, Any],
) -> dict[str, Any]:
    return {
        **metadata,
        "endpoint_ref_normalization": "resolved_entity_map",
        "original_endpoint_refs": original,
        "normalized_endpoint_refs": normalized,
    }


def _issue(
    field_path: str,
    message: str,
    code: str,
    details: dict[str, Any] | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        field_path=field_path,
        message=message,
        code=code,
        details=details or {},
    )
