from __future__ import annotations

from collections import defaultdict
from typing import Any

from my_digital_brain.ingestion.contracts import (
    ClarificationRequest,
    ExtractionPlan,
    ExtractionTask,
    IngestionContextPackage,
    Mention,
    MentionScan,
    SourceRecordRef,
)
from my_digital_brain.ingestion.contracts.drafts import (
    ClarificationRequestDraft,
    SemanticIngestionActionDraft,
    SemanticIngestionPlanDraft,
)
from my_digital_brain.ingestion.enums import (
    ExtractionExecutionMode,
    ExtractionTaskType,
    MentionKind,
)
from my_digital_brain.ingestion.ontology import (
    ACTION_KIND_TO_TASKS,
    ANCHOR_MENTION_TO_TASK,
    REF_CONSUMING_TASK_TYPES,
    REF_PRODUCING_TASK_TYPES,
    SemanticActionKind,
    ontology_prompt_payload,
)


class SemanticExtractionTaskCompiler:
    """Compile semantic planner actions into backend-compatible extraction tasks."""

    def compile(
        self,
        draft: SemanticIngestionPlanDraft,
        source: SourceRecordRef,
        mention_scan: MentionScan,
        context: IngestionContextPackage,
    ) -> ExtractionPlan:
        if draft.execution_mode == ExtractionExecutionMode.NEEDS_CLARIFICATION_FIRST:
            return self._clarification_plan(draft, source, context)
        if draft.execution_mode == ExtractionExecutionMode.NEEDS_CONTEXT_EXPANSION:
            return ExtractionPlan(
                source_id=source.source_id,
                context_package_id=context.context_package_id,
                execution_mode=draft.execution_mode,
                reason=draft.reason,
                context_gaps=list(draft.context_gaps),
                metadata=self._plan_metadata(draft, mention_scan),
            )

        ordered_actions = self._ordered_actions(draft.actions)
        mention_refs = self._mention_ref_catalog(mention_scan)
        tasks: list[ExtractionTask] = []
        for action_index, action in enumerate(ordered_actions, start=1):
            for task_type in self._task_types_for_action(action, mention_scan):
                suggested_refs = mention_refs.get(task_type, [])
                tasks.append(
                    ExtractionTask(
                        task_type=task_type,
                        target_ref=None,
                        evidence_text=action.evidence_text,
                        source_refs=[source.source_id],
                        expected_output=_expected_output(task_type),
                        required_context_refs=list(action.context_refs),
                        notes=action.notes or action.goal,
                        metadata={
                            "schema_layer": "backend_compiled",
                            "semantic_action_ref": action.action_ref,
                            "semantic_action_kind": SemanticActionKind(
                                action.action_kind,
                            ).value,
                            "semantic_action_goal": action.goal,
                            "semantic_action_index": action_index,
                            "semantic_depends_on": list(action.depends_on),
                            "semantic_concepts": list(action.concepts),
                            "ref_policy": (
                                "may_create_refs"
                                if task_type in REF_PRODUCING_TASK_TYPES
                                else "use_allowed_refs_only"
                            ),
                            "suggested_candidate_refs": suggested_refs,
                            "ontology": ontology_prompt_payload(),
                        },
                    )
                )

        tasks = self._phase_ordered_tasks(tasks)
        return ExtractionPlan(
            source_id=source.source_id,
            context_package_id=context.context_package_id,
            execution_mode=draft.execution_mode,
            reason=draft.reason,
            tasks=tasks,
            clarification=(
                self._clarification(draft.clarification)
                if draft.clarification is not None
                else None
            ),
            context_gaps=list(draft.context_gaps),
            metadata=self._plan_metadata(draft, mention_scan),
        )

    def _clarification_plan(
        self,
        draft: SemanticIngestionPlanDraft,
        source: SourceRecordRef,
        context: IngestionContextPackage,
    ) -> ExtractionPlan:
        return ExtractionPlan(
            source_id=source.source_id,
            context_package_id=context.context_package_id,
            execution_mode=draft.execution_mode,
            reason=draft.reason,
            clarification=self._clarification(draft.clarification),
            context_gaps=list(draft.context_gaps),
            metadata=self._plan_metadata(draft, None),
        )

    def _clarification(
        self,
        draft: ClarificationRequestDraft | None,
    ) -> ClarificationRequest | None:
        if draft is None:
            return None
        return ClarificationRequest(
            question=draft.question,
            reason=draft.reason,
            target_refs=list(draft.target_refs),
            options=list(draft.options),
            free_text_allowed=draft.free_text_allowed,
            blocking=draft.blocking,
            metadata={"schema_layer": "backend_compiled"},
        )

    def _ordered_actions(
        self,
        actions: list[SemanticIngestionActionDraft],
    ) -> list[SemanticIngestionActionDraft]:
        return sorted(
            actions,
            key=lambda action: (
                0
                if SemanticActionKind(action.action_kind)
                in {
                    SemanticActionKind.EXTRACT_ANCHORS,
                    SemanticActionKind.EXTRACT_EVENT,
                }
                else 1,
                action.action_ref,
            ),
        )

    def _task_types_for_action(
        self,
        action: SemanticIngestionActionDraft,
        mention_scan: MentionScan,
    ) -> list[ExtractionTaskType]:
        action_kind = SemanticActionKind(action.action_kind)
        if action_kind == SemanticActionKind.EXTRACT_ANCHORS:
            kinds = [
                MentionKind(kind)
                for kind in action.concept_kinds
                if MentionKind(kind) in ANCHOR_MENTION_TO_TASK
            ]
            if not kinds:
                kinds = [
                    mention.kind
                    for mention in mention_scan.mentions
                    if mention.kind in ANCHOR_MENTION_TO_TASK
                ]
            return _dedupe([ANCHOR_MENTION_TO_TASK[kind] for kind in kinds])
        return list(ACTION_KIND_TO_TASKS[action_kind])

    def _mention_ref_catalog(
        self,
        mention_scan: MentionScan,
    ) -> dict[ExtractionTaskType, list[dict[str, Any]]]:
        by_task: dict[ExtractionTaskType, list[dict[str, Any]]] = defaultdict(list)
        counters: dict[ExtractionTaskType, int] = defaultdict(int)
        for mention in mention_scan.mentions:
            task_type = ANCHOR_MENTION_TO_TASK.get(mention.kind)
            if task_type is None:
                continue
            counters[task_type] += 1
            by_task[task_type].append(
                {
                    "local_ref": _candidate_ref(task_type, counters[task_type]),
                    "mention_text": mention.text,
                    "evidence_text": mention.evidence_text or mention.text,
                    "mention_kind": str(mention.kind),
                }
            )
        return dict(by_task)

    def _phase_ordered_tasks(self, tasks: list[ExtractionTask]) -> list[ExtractionTask]:
        return sorted(
            tasks,
            key=lambda task: (
                0
                if ExtractionTaskType(task.task_type) in REF_PRODUCING_TASK_TYPES
                else 1,
                0
                if ExtractionTaskType(task.task_type) not in REF_CONSUMING_TASK_TYPES
                else 1,
                str(ExtractionTaskType(task.task_type)),
                task.task_id,
            ),
        )

    def _plan_metadata(
        self,
        draft: SemanticIngestionPlanDraft,
        mention_scan: MentionScan | None,
    ) -> dict[str, Any]:
        return {
            "schema_layer": "backend_compiled",
            "semantic_plan": draft.model_dump(mode="json", exclude_none=True),
            "semantic_action_count": len(draft.actions),
            "mention_count": len(mention_scan.mentions) if mention_scan is not None else None,
            "ontology": ontology_prompt_payload(),
        }


def _candidate_ref(task_type: ExtractionTaskType, index: int) -> str:
    suffix = ExtractionTaskType(task_type).value.upper()
    return f"CANDIDATE_{suffix}_{index:03d}"


def _expected_output(task_type: ExtractionTaskType) -> str:
    expectations = {
        ExtractionTaskType.RELATIONSHIP: (
            "Extract structural links using allowed relationship_type enum values. "
            "For social relationships use RELATIONSHIP_WITH plus relationship_kind."
        ),
        ExtractionTaskType.RELATIONSHIP_CONTEXT: (
            "Extract relationship context, current status, affective meaning, "
            "relationship_kind, and source-grounded relationship_detail."
        ),
        ExtractionTaskType.PERCEPTION: "Extract subjective perception and affective context.",
        ExtractionTaskType.CLAIM: "Extract atomic factual claims and their about refs.",
        ExtractionTaskType.METADATA_PATCH: "Extract scoped property update suggestions.",
    }
    return expectations.get(
        task_type,
        "Extract candidate anchors using only the allowed entity_type enum.",
    )


def _dedupe(values: list[ExtractionTaskType]) -> list[ExtractionTaskType]:
    seen: set[ExtractionTaskType] = set()
    result: list[ExtractionTaskType] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
