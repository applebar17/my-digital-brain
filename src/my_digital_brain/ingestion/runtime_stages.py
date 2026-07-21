"""Planning and extraction stages for the reasoning-first ingestion runtime."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from my_digital_brain.agentic import (
    AgenticMemoryLogExtractionService,
    AgenticToolExecutionContext,
    ReasoningCheckpointContext,
    ReasoningPurposeGuidelines,
)
from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    CandidateMemoryGraph,
    CandidateOutput,
    EntityIngestionPlanDraft,
    ExtractionPlan,
    ExtractionTask,
    GraphContextPack,
    IngestionReasoningCheckpointDraft,
    IngestionResult,
    MemoryLog,
    MemoryLogDraftBatch,
    MemoryLogIngestionPlanDraft,
    RelationshipIngestionPlanDraft,
    ResolvedEntityMap,
    SourceRecordRef,
    ValidationIssue,
)
from my_digital_brain.ingestion.enrichment import enrich_memory_log_batch_with_tasks
from my_digital_brain.ingestion.planning_contexts import (
    build_entity_planning_context,
    build_memory_log_extraction_batch_context,
    build_memory_log_planning_context,
    build_missing_entity_planning_context,
    build_relationship_planning_context,
)
from my_digital_brain.ingestion.protocols import FocusedExtractor
from my_digital_brain.ingestion.refined_relationships import normalize_relationship_candidate_refs
from my_digital_brain.ingestion.runtime_helpers import (
    batch_extraction_items as _batch_extraction_items,
)
from my_digital_brain.ingestion.runtime_helpers import (
    batch_sequence as _batch_sequence,
)
from my_digital_brain.ingestion.runtime_helpers import (
    combined_extraction_plan as _combined_extraction_plan,
)
from my_digital_brain.ingestion.runtime_helpers import (
    context_package_for_services as _context_package_for_services,
)
from my_digital_brain.ingestion.runtime_helpers import (
    extract_with_optional_batch as _extract_with_optional_batch,
)
from my_digital_brain.ingestion.runtime_helpers import (
    structured_step_failure as _structured_step_failure,
)
from my_digital_brain.ingestion.runtime_helpers import (
    timezone_for_source as _timezone,
)


class IngestionPlanningMixin:
    def _reason(
        self,
        source: SourceRecordRef,
        graph_context_pack: GraphContextPack,
        graph_context_view,
    ) -> IngestionReasoningCheckpointDraft | IngestionResult:
        context = ReasoningCheckpointContext(
            purpose=ReasoningPurposeGuidelines(
                purpose_id="ingestion_reasoning_checkpoint",
                goal="Interpret source text before entity and relationship planning.",
                focus_areas=[
                    "entity identity",
                    "aliases",
                    "duplicate hints",
                    "relationships",
                    "node versus detail",
                    "user/owner perspective",
                ],
                forbidden_assumptions=[
                    "Do not treat aliases as identity.",
                    "Do not invent graph refs.",
                ],
            ),
            input_context={
                "source_text": source.raw_text or source.content_ref or "",
                "graph_context_view": graph_context_view.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
            },
            timezone=_timezone(source),
            metadata={"graph_context_pack_id": graph_context_pack.context_pack_id},
        )
        result = self.reasoning_service.reason(
            context,
            self._execution_context(source),
            output_schema=IngestionReasoningCheckpointDraft,
        )
        _raise_if_interrupted(result)
        if result.status != "ok" or result.structured_output is None:
            return _structured_step_failure(
                source,
                "reasoning",
                result.assistant_text or "Reasoning checkpoint failed.",
            )
        return IngestionReasoningCheckpointDraft.model_validate(result.structured_output)

    def _plan_entities(
        self,
        source: SourceRecordRef,
        reasoning: IngestionReasoningCheckpointDraft,
        graph_context_view,
    ) -> EntityIngestionPlanDraft | IngestionResult:
        context = build_entity_planning_context(
            source_text=source.raw_text or source.content_ref or "",
            graph_context_view=graph_context_view,
            reasoning=reasoning,
            timezone=_timezone(source),
        )
        result = self.planning_service.plan(
            context,
            self._execution_context(source),
            output_schema=EntityIngestionPlanDraft,
        )
        _raise_if_interrupted(result)
        if result.status != "ok" or result.structured_output is None:
            return _structured_step_failure(
                source,
                "entity_planning",
                result.assistant_text or "Entity planning failed.",
            )
        return EntityIngestionPlanDraft.model_validate(result.structured_output)

    def _plan_relationships(
        self,
        source: SourceRecordRef,
        reasoning: IngestionReasoningCheckpointDraft,
        graph_context_view,
        resolved_entity_map,
        entity_packet: list[dict[str, Any]] | None = None,
        memory_log_packet: list[dict[str, Any]] | None = None,
    ) -> RelationshipIngestionPlanDraft | IngestionResult:
        context = build_relationship_planning_context(
            source_text=source.raw_text or source.content_ref or "",
            graph_context_view=graph_context_view,
            reasoning=reasoning,
            resolved_entity_map=resolved_entity_map,
            entity_packet=entity_packet,
            memory_log_packet=memory_log_packet,
            timezone=_timezone(source),
        )
        result = self.planning_service.plan(
            context,
            self._execution_context(source),
            output_schema=RelationshipIngestionPlanDraft,
        )
        _raise_if_interrupted(result)
        if result.status != "ok" or result.structured_output is None:
            return _structured_step_failure(
                source,
                "relationship_planning",
                result.assistant_text or "Relationship planning failed.",
            )
        return RelationshipIngestionPlanDraft.model_validate(result.structured_output)

    def _plan_memory_logs(
        self,
        source: SourceRecordRef,
        reasoning: IngestionReasoningCheckpointDraft,
        graph_context_view,
        resolved_entity_map: ResolvedEntityMap,
        entity_packet: list[dict[str, Any]],
    ) -> MemoryLogIngestionPlanDraft | IngestionResult:
        context = build_memory_log_planning_context(
            source_text=source.raw_text or source.content_ref or "",
            graph_context_view=graph_context_view,
            reasoning=reasoning,
            resolved_entity_map=resolved_entity_map,
            entity_packet=entity_packet,
            timezone=_timezone(source),
        )
        result = self.planning_service.plan(
            context,
            self._execution_context(source),
            output_schema=MemoryLogIngestionPlanDraft,
        )
        _raise_if_interrupted(result)
        if result.status != "ok" or result.structured_output is None:
            return _structured_step_failure(
                source,
                "memory_log_planning",
                result.assistant_text or "Memory-log planning failed.",
            )
        return MemoryLogIngestionPlanDraft.model_validate(result.structured_output)

    def _plan_missing_entity(
        self,
        source: SourceRecordRef,
        reasoning: IngestionReasoningCheckpointDraft,
        graph_context_view,
        missing_entity,
        resolved_entity_map: ResolvedEntityMap,
    ) -> EntityIngestionPlanDraft | IngestionResult:
        context = build_missing_entity_planning_context(
            source_text=source.raw_text or source.content_ref or "",
            graph_context_view=graph_context_view,
            reasoning=reasoning,
            missing_entity=missing_entity,
            resolved_entity_map=resolved_entity_map,
            timezone=_timezone(source),
        )
        result = self.planning_service.plan(
            context,
            self._execution_context(source),
            output_schema=EntityIngestionPlanDraft,
        )
        _raise_if_interrupted(result)
        if result.status != "ok" or result.structured_output is None:
            return _structured_step_failure(
                source,
                "missing_entity_planning",
                result.assistant_text or "Missing-entity planning failed.",
            )
        return EntityIngestionPlanDraft.model_validate(result.structured_output)


class IngestionExtractionMixin:
    def _extract_memory_logs(
        self,
        source: SourceRecordRef,
        graph_context_pack: GraphContextPack,
        graph_context_view,
        reasoning: IngestionReasoningCheckpointDraft,
        resolved_entity_map: ResolvedEntityMap,
        entity_packet: list[dict[str, Any]],
        memory_log_plan: MemoryLogIngestionPlanDraft,
        extraction_plan: ExtractionPlan,
    ) -> tuple[list[MemoryLog], list[ValidationIssue]]:
        memory_logs: list[MemoryLog] = []
        issues: list[ValidationIssue] = []
        action_by_ref: dict[str, tuple[int, Any, Any, int]] = {}
        for action_index, action in enumerate(memory_log_plan.actions, start=1):
            for memory_log_index, planned_memory_log in enumerate(
                action.memory_logs,
                start=1,
            ):
                action_by_ref[planned_memory_log.local_ref] = (
                    action_index,
                    action,
                    planned_memory_log,
                    memory_log_index,
                )

        pending: list[tuple[int, ExtractionTask, Any, Any, int]] = []
        for index, task in enumerate(extraction_plan.tasks):
            planned = action_by_ref.get(task.target_ref or "")
            if planned is None:
                issues.append(
                    ValidationIssue(
                        field_path=f"memory_log_extraction_plan.tasks[{index}]",
                        message="Memory-log extraction task is missing its planned target.",
                        code="missing_memory_log_planned_target",
                        details={"task_id": task.task_id, "target_ref": task.target_ref},
                    ),
                )
                continue
            _, action, planned_memory_log, memory_log_index = planned
            pending.append((index, task, action, planned_memory_log, memory_log_index))

        extraction_service = (
            self.memory_log_extraction_service
            or AgenticMemoryLogExtractionService(self.planning_service.state_runner)
        )
        for batch in _batch_sequence(
            pending,
            self.extraction_draft_batch_size,
        ):
            first_index = batch[0][0]
            tasks = [item[1] for item in batch]
            planned_items = [(item[2], item[3], item[4]) for item in batch]
            context = build_memory_log_extraction_batch_context(
                source_text=source.raw_text or source.content_ref or "",
                graph_context_view=graph_context_view,
                resolved_entity_map=resolved_entity_map,
                entity_packet=entity_packet,
                planned_items=planned_items,
                timezone=_timezone(source),
            )
            result = extraction_service.extract(
                context,
                self._execution_context(source),
                output_schema=MemoryLogDraftBatch,
            )
            _raise_if_interrupted(result)
            if result.status != "ok" or result.structured_output is None:
                issues.append(
                    ValidationIssue(
                        field_path=f"memory_log_extraction_plan.tasks[{first_index}]",
                        message=result.assistant_text or "Memory-log extraction failed.",
                        code="memory_log_extraction_failed",
                        details={
                            "task_ids": [task.task_id for task in tasks],
                            "target_refs": [task.target_ref for task in tasks],
                        },
                    ),
                )
                continue
            draft_batch = MemoryLogDraftBatch.model_validate(result.structured_output)
            extracted = enrich_memory_log_batch_with_tasks(draft_batch, source, tasks)
            if len(extracted) != len(tasks):
                issues.append(
                    ValidationIssue(
                        field_path=f"memory_log_extraction_plan.tasks[{first_index}]",
                        message=(
                            "Memory-log extraction must return exactly one MemoryLog "
                            "draft per planned target."
                        ),
                        code="unexpected_memory_log_candidate_count",
                        details={
                            "task_ids": [task.task_id for task in tasks],
                            "target_refs": [task.target_ref for task in tasks],
                            "expected_count": len(tasks),
                            "count": len(extracted),
                        },
                    ),
                )
                continue
            memory_logs.extend(extracted)
        return memory_logs, issues

    def _extract_entities(
        self,
        source: SourceRecordRef,
        graph_context_pack: GraphContextPack,
        extraction_plan: ExtractionPlan,
    ) -> tuple[list[CandidateEntity], list[ValidationIssue]]:
        candidates: list[CandidateEntity] = []
        issues: list[ValidationIssue] = []
        context = _context_package_for_services(source, graph_context_pack)
        pending: list[tuple[int, ExtractionTask, FocusedExtractor]] = []
        for index, task in enumerate(extraction_plan.tasks):
            extractor = self._find_entity_extractor(task)
            if extractor is None:
                issues.append(
                    ValidationIssue(
                        field_path=f"entity_extraction_plan.tasks[{index}]",
                        message=(
                            f"No entity extractor registered for task type '{task.task_type}'."
                        ),
                        code="missing_ingestion_entity_extractor",
                        details={
                            "task_id": task.task_id,
                            "task_type": str(task.task_type),
                        },
                    ),
                )
                continue
            pending.append((index, task, extractor))
        for batch in _batch_extraction_items(
            pending,
            self.extraction_draft_batch_size,
        ):
            first_index = batch[0][0]
            extractor = batch[0][2]
            tasks = [item[1] for item in batch]
            extracted = _extract_with_optional_batch(extractor, source, tasks, context)
            for candidate in extracted:
                if isinstance(candidate, CandidateEntity):
                    candidates.append(candidate)
                else:
                    issues.append(
                        ValidationIssue(
                            field_path=f"entity_extraction_plan.tasks[{first_index}]",
                            message="Entity extraction returned a non-entity candidate.",
                            code="unexpected_ingestion_entity_candidate_type",
                            details={
                                "task_ids": [task.task_id for task in tasks],
                                "candidate_type": type(candidate).__name__,
                            },
                        ),
                    )
        return candidates, issues

    def _extract_relationship_candidates(
        self,
        source: SourceRecordRef,
        graph_context_pack: GraphContextPack,
        extraction_plan: ExtractionPlan,
        resolved_entity_map: ResolvedEntityMap,
    ) -> tuple[list[CandidateOutput], list[ValidationIssue]]:
        candidates: list[CandidateOutput] = []
        issues: list[ValidationIssue] = []
        context = _context_package_for_services(source, graph_context_pack)
        pending: list[tuple[int, ExtractionTask, FocusedExtractor]] = []
        for index, task in enumerate(extraction_plan.tasks):
            extractor = self._find_relationship_extractor(task)
            if extractor is None:
                issues.append(
                    ValidationIssue(
                        field_path=f"relationship_extraction_plan.tasks[{index}]",
                        message=(
                            f"No relationship extractor registered for task type "
                            f"'{task.task_type}'."
                        ),
                        code="missing_ingestion_relationship_extractor",
                        details={
                            "task_id": task.task_id,
                            "task_type": str(task.task_type),
                        },
                    ),
                )
                continue
            pending.append((index, task, extractor))
        for batch in _batch_extraction_items(
            pending,
            self.extraction_draft_batch_size,
        ):
            first_index = batch[0][0]
            extractor = batch[0][2]
            tasks = [item[1] for item in batch]
            extracted = normalize_relationship_candidate_refs(
                _extract_with_optional_batch(extractor, source, tasks, context),
                resolved_entity_map,
            )
            for candidate in extracted:
                if isinstance(candidate, CandidateEntity):
                    issues.append(
                        ValidationIssue(
                            field_path=f"relationship_extraction_plan.tasks[{first_index}]",
                            message="Relationship extraction returned an entity candidate.",
                            code="unexpected_ingestion_relationship_candidate_type",
                            details={
                                "task_ids": [task.task_id for task in tasks],
                                "candidate_type": type(candidate).__name__,
                            },
                        ),
                    )
                else:
                    candidates.append(candidate)
        return candidates, issues

    def _find_entity_extractor(self, task: ExtractionTask) -> FocusedExtractor | None:
        for extractor in self.entity_extractors:
            if extractor.supports(task):
                return extractor
        return None

    def _find_relationship_extractor(self, task: ExtractionTask) -> FocusedExtractor | None:
        for extractor in self.relationship_extractors:
            if extractor.supports(task):
                return extractor
        return None

    def _assemble_final_candidate_graph(
        self,
        source: SourceRecordRef,
        graph_context_pack: GraphContextPack,
        entity_extraction_plan: ExtractionPlan,
        supplemental_extraction_plans: Sequence[ExtractionPlan],
        relationship_extraction_plan: ExtractionPlan | None,
        candidates: Sequence[CandidateOutput],
    ) -> CandidateMemoryGraph:
        plans: list[ExtractionPlan] = [
            entity_extraction_plan,
            *supplemental_extraction_plans,
        ]
        if relationship_extraction_plan is not None:
            plans.append(relationship_extraction_plan)
        combined_plan = _combined_extraction_plan(source, graph_context_pack, plans)
        return self.assembler.assemble(source, combined_plan, candidates)

    def _execution_context(self, source: SourceRecordRef) -> AgenticToolExecutionContext:
        context = (
            self.execution_context_factory(source)
            if self.execution_context_factory is not None
            else AgenticToolExecutionContext()
        )
        context.current_text = (
            str(source.metadata.get("current_user_message") or "").strip()
            or source.raw_text
            or source.content_ref
        )
        context.metadata = {
            **context.metadata,
            "source_id": source.source_id,
            "reasoning_first_ingestion": True,
        }
        return context


def _raise_if_interrupted(result: Any) -> None:
    if getattr(result, "status", None) != "interrupted":
        return
    raise RuntimeError(
        "The ingestion step is awaiting an external tool interaction: "
        f"{getattr(result, 'assistant_text', None) or 'answer the pending tool request'}"
    )
