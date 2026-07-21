"""Final proposal compilation, write planning, execution, and result recording."""

from __future__ import annotations

import json
import logging
from typing import Any

from my_digital_brain.ai.tracing import traceable
from my_digital_brain.ai.logging import log_event
from my_digital_brain.debug import AIFlowTraceSection, record_ai_flow_event
from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    CandidateMemoryGraph,
    CandidateOutput,
    EntityIngestionPlanDraft,
    ExtractionPlan,
    GraphContextPack,
    IngestionReasoningCheckpointDraft,
    IngestionResult,
    MemoryLog,
    MemoryLogIngestionPlanDraft,
    RelationshipIngestionPlanDraft,
    ResolvedEntityMap,
    SourceRecordRef,
    ValidationIssue,
    ResolutionStep,
)
from my_digital_brain.ingestion.enums import IngestionStatus
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry
from my_digital_brain.ingestion.resolution_proposals import (
    ResolutionProposalCompiler,
    ResolutionProposalValidationError,
    ResolutionProposalValidator,
)
from my_digital_brain.ingestion.runtime_helpers import (
    context_package_for_services as _context_package_for_services,
    validation_issue_summaries as _validation_issue_summaries,
    write_plan_counts as _write_plan_counts,
    write_plan_has_mutations as _write_plan_has_mutations,
)

logger = logging.getLogger(__name__)


class IngestionCompletionMixin:
    """Complete a candidate graph using only validated structured actions."""

    def _complete_write(
        self,
        *,
        source: SourceRecordRef,
        graph_context_pack: GraphContextPack,
        graph_context_views: dict[str, Any],
        reasoning: IngestionReasoningCheckpointDraft,
        entity_plan: EntityIngestionPlanDraft | None,
        entity_extraction_plan: ExtractionPlan,
        entity_candidates: list[CandidateEntity],
        entity_candidate_graph: CandidateMemoryGraph,
        supplemental_entity_plans: list[EntityIngestionPlanDraft],
        supplemental_entity_extraction_plans: list[ExtractionPlan],
        supplemental_entity_candidates: list[CandidateEntity],
        resolved_entity_map: ResolvedEntityMap,
        memory_log_plan: MemoryLogIngestionPlanDraft,
        memory_log_extraction_plan: ExtractionPlan,
        memory_logs: list[MemoryLog],
        relationship_plan: RelationshipIngestionPlanDraft,
        relationship_extraction_plan: ExtractionPlan,
        relationship_candidates: list[CandidateOutput],
        candidate_graph: CandidateMemoryGraph,
    ) -> IngestionResult:
        checkpoint_fields = {
            "graph_context_pack": graph_context_pack,
            "graph_context_views": graph_context_views,
            "reasoning": reasoning,
            "entity_plan": entity_plan,
            "entity_extraction_plan": entity_extraction_plan,
            "entity_candidates": entity_candidates,
            "entity_candidate_graph": entity_candidate_graph,
            "supplemental_entity_plans": supplemental_entity_plans,
            "supplemental_entity_extraction_plans": supplemental_entity_extraction_plans,
            "supplemental_entity_candidates": supplemental_entity_candidates,
            "resolved_entity_map": resolved_entity_map,
            "memory_log_plan": memory_log_plan,
            "memory_log_extraction_plan": memory_log_extraction_plan,
            "memory_logs": memory_logs,
            "relationship_plan": relationship_plan,
            "relationship_extraction_plan": relationship_extraction_plan,
            "relationship_candidates": relationship_candidates,
            "candidate_graph": candidate_graph,
        }
        context = _context_package_for_services(source, graph_context_pack)

        if self.write_plan_builder is None:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.CANDIDATE_READY,
                    **checkpoint_fields,
                    metadata={"ingestion_stage": "candidate_graph_ready"},
                ),
            )
        if self.resolution_agent is None:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    **checkpoint_fields,
                    validation_errors=[
                        ValidationIssue(
                            field_path="resolution_agent",
                            message=(
                                "A complete structured resolution proposal is required "
                                "before graph write planning."
                            ),
                            code="resolution_agent_required",
                        ),
                    ],
                    metadata={"ingestion_stage": "resolution_agent_required"},
                ),
            )

        try:
            registry = RunReferenceRegistry.from_snapshot(
                context.reference_registry_snapshot,
            )
            compiler = ResolutionProposalCompiler(ResolutionProposalValidator(registry))
            resolution = compiler.result_from_entity_map(resolved_entity_map)
            for step, candidates in (
                (
                    ResolutionStep.MEMORY,
                    [*candidate_graph.memory_logs, *candidate_graph.candidate_profile_memories],
                ),
                (
                    ResolutionStep.RELATIONSHIP,
                    [
                        *candidate_graph.candidate_relationships,
                        *candidate_graph.candidate_relationship_contexts,
                    ],
                ),
            ):
                if not candidates:
                    continue
                actions = self.resolution_agent.propose(
                    step=step,
                    source_text=source.raw_text,
                    context=context,
                    candidate_graph=candidate_graph,
                    packets=context.identity_lookup_packets,
                )
                resolution = compiler.merge_step_actions(
                    resolution,
                    actions,
                    step=step,
                    supplied_candidate_refs=[
                        candidate.local_ref
                        for candidate in [*candidate_graph.candidate_entities, *candidates]
                        if candidate.local_ref
                    ],
                    action_candidate_refs=[candidate.local_ref for candidate in candidates],
                    packets=context.identity_lookup_packets,
                )
        except (ResolutionProposalValidationError, ValueError) as exc:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    **checkpoint_fields,
                    validation_errors=[
                        ValidationIssue(
                            field_path="resolution_result",
                            message=str(exc),
                            code="resolution_result_compilation_failed",
                        ),
                    ],
                    metadata={"ingestion_stage": "resolution_result_compilation"},
                ),
            )
        if resolution.clarifications:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.NEEDS_CLARIFICATION,
                    **checkpoint_fields,
                    clarification=resolution.clarification,
                    clarifications=resolution.clarifications,
                    metadata={"ingestion_stage": "write_resolution_clarification"},
                ),
            )

        try:
            write_plan = self.write_plan_builder.build(candidate_graph, resolution, context)
        except Exception as exc:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    **checkpoint_fields,
                    validation_errors=[
                        ValidationIssue(
                            field_path="write_plan",
                            message=str(exc),
                            code="write_plan_build_failed",
                        ),
                    ],
                    metadata={"ingestion_stage": "write_plan_build"},
                ),
            )

        if not _write_plan_has_mutations(write_plan):
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    **checkpoint_fields,
                    write_plan=write_plan,
                    validation_errors=[
                        ValidationIssue(
                            field_path="write_plan",
                            message=(
                                "The resolved write plan contains no graph mutations. "
                                "Memory storage requires at least one durable write."
                            ),
                            code="empty_write_plan",
                        ),
                    ],
                    metadata={"ingestion_stage": "write_plan_validation"},
                ),
            )

        write_validation = self.validator.validate_write_plan(write_plan)
        if not write_validation.is_valid:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    **checkpoint_fields,
                    write_plan=write_plan,
                    validation_errors=write_validation.issues,
                    metadata={"ingestion_stage": "write_plan_validation"},
                ),
            )

        if self.write_plan_executor is None or not self.execute_write_plan:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.WRITE_PLAN_READY,
                    **checkpoint_fields,
                    write_plan=write_plan,
                    metadata={
                        "ingestion_stage": "write_plan_ready",
                        "write_counts": _write_plan_counts(write_plan),
                    },
                ),
            )

        execution = self.write_plan_executor.execute(write_plan)
        execution = execution.model_copy(
            update={
                **checkpoint_fields,
                "write_plan": execution.write_plan or write_plan,
                "metadata": {
                    **execution.metadata,
                    "ingestion_stage": "write_executed",
                    "write_counts": _write_plan_counts(execution.write_plan or write_plan),
                },
            },
            deep=True,
        )
        if execution.status == IngestionStatus.WRITTEN:
            self._vectorize_written_result(execution)
        return self._finish(execution)

    def _finish(self, result: IngestionResult) -> IngestionResult:
        if result.validation_errors:
            log_event(
                logger,
                "ingestion.validation_failed",
                level="warning",
                component="ingestion",
                source_id=result.source_id,
                ingestion_id=result.ingestion_id,
                status=str(result.status),
                validation_error_count=len(result.validation_errors),
                validation_errors=_validation_issue_summaries(result.validation_errors),
            )
        log_event(
            logger,
            "ingestion.result",
            component="ingestion",
            source_id=result.source_id,
            ingestion_id=result.ingestion_id,
            status=str(result.status),
            ingestion_stage=result.metadata.get("ingestion_stage"),
            validation_error_count=len(result.validation_errors),
            validation_error_codes=[
                issue.code for issue in result.validation_errors if issue.code
            ],
            has_clarification=result.clarification is not None,
            write_counts=_write_plan_counts(result.write_plan) if result.write_plan else None,
        )
        if result.clarification is not None or result.clarifications:
            log_event(
                logger,
                "ingestion.clarification.requested",
                component="ingestion",
                source_id=result.source_id,
                ingestion_id=result.ingestion_id,
                clarification_count=max(
                    len(result.clarifications),
                    1 if result.clarification is not None else 0,
                ),
                ingestion_stage=result.metadata.get("ingestion_stage"),
            )
        if self.process_store is not None:
            self.process_store.record_result(result)
        record_ai_flow_event(
            title="Ingestion Backend Result",
            call_kind="backend_process_result",
            purpose="memory_ingestion",
            status=str(result.status),
            sections=[
                AIFlowTraceSection(
                    title="TOOL OUTPUT",
                    content=json.dumps(
                        {
                            "status": str(result.status),
                            "source_id": result.source_id,
                            "ingestion_id": result.ingestion_id,
                            "ingestion_stage": result.metadata.get("ingestion_stage"),
                            "has_clarification": result.clarification is not None,
                            "validation_errors": _validation_issue_summaries(
                                result.validation_errors,
                            ),
                            "write_counts": (
                                _write_plan_counts(result.write_plan)
                                if result.write_plan
                                else None
                            ),
                        },
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    ),
                    content_type="json",
                ),
            ],
            metadata={
                "source_id": result.source_id,
                "ingestion_id": result.ingestion_id,
                "status": str(result.status),
            },
        )
        return result

    @traceable(name="Ingestion Vectorize Written Result", run_type="chain")
    def _vectorize_written_result(self, result: IngestionResult) -> None:
        if self.vectorization_service is None:
            return
        try:
            vectorization = self.vectorization_service.vectorize_ingestion_result(result)
            if hasattr(vectorization, "model_dump"):
                payload = vectorization.model_dump(mode="json", exclude_none=True)
            elif isinstance(vectorization, dict):
                payload = dict(vectorization)
            else:
                payload = {"result": str(vectorization)}
            result.metadata = {**result.metadata, "vectorization": payload}
            log_event(
                logger,
                "ingestion.vectorization.done",
                component="ingestion",
                source_id=result.source_id,
                ingestion_id=result.ingestion_id,
                vectorization=payload,
            )
        except Exception as exc:  # pragma: no cover - defensive around external stores
            result.metadata = {
                **result.metadata,
                "vectorization": {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            }
            log_event(
                logger,
                "ingestion.vectorization.failed",
                level="error",
                component="ingestion",
                source_id=result.source_id,
                ingestion_id=result.ingestion_id,
                error_type=type(exc).__name__,
                error=str(exc),
            )
