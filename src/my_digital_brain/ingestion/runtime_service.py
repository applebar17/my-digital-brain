from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
import json
import logging
from typing import Any

from pydantic import BaseModel

from my_digital_brain.agentic import (
    AgenticPlanningService,
    AgenticReasoningService,
    AgenticToolExecutionContext,
    ReasoningCheckpointContext,
    ReasoningPurposeGuidelines,
)
from my_digital_brain.ai.logging import log_event
from my_digital_brain.ai.tracing import traceable
from my_digital_brain.debug import AIFlowTraceSection, record_ai_flow_event
from my_digital_brain.ingestion.assembly import CandidateMemoryGraphAssembler
from my_digital_brain.ingestion.context_rendering import GraphContextPackRendererService
from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    CandidateMemoryGraph,
    CandidateOutput,
    ClarificationRequest,
    ClarificationRequestDraft,
    EntityIngestionPlanDraft,
    ExtractionPlan,
    ExtractionTask,
    GraphContextPack,
    GraphContextRenderPurpose,
    IngestionContextPackage,
    IngestionReasoningCheckpointDraft,
    IngestionResult,
    RelationshipIngestionPlanDraft,
    ResolvedEntityMap,
    SourceRecordRef,
    ValidationIssue,
)
from my_digital_brain.ingestion.enums import ExtractionExecutionMode, IngestionStatus
from my_digital_brain.ingestion.graph_context_pack import (
    WholeSourceGraphContextPackBuilder,
)
from my_digital_brain.ingestion.ontology import (
    ontology_prompt_payload,
    task_type_for_entity_type,
)
from my_digital_brain.ingestion.planning_contexts import (
    build_entity_planning_context,
    build_missing_entity_planning_context,
    build_relationship_planning_context,
)
from my_digital_brain.ingestion.protocols import (
    FocusedExtractor,
    GraphVectorizationService,
    GraphWritePlanBuilder,
    GraphWritePlanExecutor,
    IngestionProcessStore,
    ResolutionService,
)
from my_digital_brain.ingestion.refined_relationships import (
    build_relationship_extraction_plan,
    normalize_relationship_candidate_refs,
)
from my_digital_brain.ingestion.refined_resolution import (
    DeterministicResolvedEntityMapBuilder,
)
from my_digital_brain.ingestion.validation import IngestionValidator

ExecutionContextFactory = Callable[[SourceRecordRef], AgenticToolExecutionContext]
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionService:
    """Reasoning-first, entity-first ingestion runtime through durable graph write."""

    reasoning_service: AgenticReasoningService
    planning_service: AgenticPlanningService
    graph_context_builder: WholeSourceGraphContextPackBuilder
    entity_extractors: Sequence[FocusedExtractor] = field(default_factory=list)
    relationship_extractors: Sequence[FocusedExtractor] = field(default_factory=list)
    context_renderer: GraphContextPackRendererService = field(
        default_factory=GraphContextPackRendererService,
    )
    entity_resolver: DeterministicResolvedEntityMapBuilder = field(
        default_factory=DeterministicResolvedEntityMapBuilder,
    )
    assembler: CandidateMemoryGraphAssembler = field(
        default_factory=CandidateMemoryGraphAssembler
    )
    validator: IngestionValidator = field(default_factory=IngestionValidator)
    resolution_service: ResolutionService | None = None
    write_plan_builder: GraphWritePlanBuilder | None = None
    write_plan_executor: GraphWritePlanExecutor | None = None
    vectorization_service: GraphVectorizationService | None = None
    execute_write_plan: bool = False
    process_store: IngestionProcessStore | None = None
    execution_context_factory: ExecutionContextFactory | None = None

    @traceable(name="Ingestion Process Source", run_type="chain")
    def process_source(self, source: SourceRecordRef) -> IngestionResult:
        log_event(
            logger,
            "ingestion.source.start",
            component="ingestion",
            source_id=source.source_id,
            source_type=str(source.source_type),
            channel=str(source.channel),
            execute_write_plan=self.execute_write_plan,
            reasoning_first_runtime=True,
        )
        if self.process_store is not None:
            self.process_store.save_source(source)

        graph_context_pack = self.graph_context_builder.build(source)
        reasoning_view = self.context_renderer.render(
            graph_context_pack,
            GraphContextRenderPurpose.REASONING,
        )
        reasoning = self._reason(source, graph_context_pack, reasoning_view)
        if isinstance(reasoning, IngestionResult):
            return reasoning

        entity_view = self.context_renderer.render(
            graph_context_pack,
            GraphContextRenderPurpose.ENTITY_PLANNING,
        )
        entity_plan = self._plan_entities(source, reasoning, entity_view)
        if isinstance(entity_plan, IngestionResult):
            return entity_plan
        if entity_plan.clarification is not None:
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.NEEDS_CLARIFICATION,
                graph_context_pack=graph_context_pack,
                graph_context_views={
                    "reasoning": reasoning_view,
                    "entity_planning": entity_view,
                },
                reasoning=reasoning,
                entity_plan=entity_plan,
                clarification=_clarification_from_draft(entity_plan.clarification),
                metadata={"ingestion_stage": "entity_planning_clarification"},
            ))

        entity_extraction_plan = _entity_extraction_plan(
            source, graph_context_pack, entity_plan
        )
        entity_candidates, extraction_issues = self._extract_entities(
            source,
            graph_context_pack,
            entity_extraction_plan,
        )
        if extraction_issues:
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.VALIDATION_FAILED,
                graph_context_pack=graph_context_pack,
                graph_context_views={
                    "reasoning": reasoning_view,
                    "entity_planning": entity_view,
                },
                reasoning=reasoning,
                entity_plan=entity_plan,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=entity_candidates,
                validation_errors=extraction_issues,
                metadata={"ingestion_stage": "entity_candidate_preparation"},
            ))

        candidate_graph = self.assembler.assemble(
            source,
            entity_extraction_plan,
            entity_candidates,
        )
        validation = self.validator.validate_candidate_graph(candidate_graph)
        if not validation.is_valid:
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.VALIDATION_FAILED,
                graph_context_pack=graph_context_pack,
                graph_context_views={
                    "reasoning": reasoning_view,
                    "entity_planning": entity_view,
                },
                reasoning=reasoning,
                entity_plan=entity_plan,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=entity_candidates,
                entity_candidate_graph=candidate_graph,
                validation_errors=validation.issues,
                metadata={"ingestion_stage": "entity_validation"},
            ))

        resolved_entity_map = self.entity_resolver.resolve(
            entity_candidates, graph_context_pack
        )
        relationship_view = self.context_renderer.render(
            graph_context_pack,
            GraphContextRenderPurpose.RELATIONSHIP_PLANNING,
        )
        relationship_plan = self._plan_relationships(
            source,
            reasoning,
            relationship_view,
            resolved_entity_map,
        )
        if isinstance(relationship_plan, IngestionResult):
            return relationship_plan
        if relationship_plan.clarification is not None:
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.NEEDS_CLARIFICATION,
                graph_context_pack=graph_context_pack,
                graph_context_views={
                    "reasoning": reasoning_view,
                    "entity_planning": entity_view,
                    "relationship_planning": relationship_view,
                },
                reasoning=reasoning,
                entity_plan=entity_plan,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=entity_candidates,
                entity_candidate_graph=candidate_graph,
                resolved_entity_map=resolved_entity_map,
                relationship_plan=relationship_plan,
                clarification=_clarification_from_draft(
                    relationship_plan.clarification
                ),
                metadata={"ingestion_stage": "relationship_planning_clarification"},
            ))

        return self._complete_relationship_candidate_preparation(
            source=source,
            graph_context_pack=graph_context_pack,
            graph_context_views={
                "reasoning": reasoning_view,
                "entity_planning": entity_view,
                "relationship_planning": relationship_view,
            },
            reasoning=reasoning,
            entity_plan=entity_plan,
            entity_extraction_plan=entity_extraction_plan,
            entity_candidates=entity_candidates,
            entity_candidate_graph=candidate_graph,
            resolved_entity_map=resolved_entity_map,
            relationship_plan=relationship_plan,
        )

    def _complete_relationship_candidate_preparation(
        self,
        *,
        source: SourceRecordRef,
        graph_context_pack: GraphContextPack,
        graph_context_views: dict[str, Any],
        reasoning: IngestionReasoningCheckpointDraft,
        entity_plan: EntityIngestionPlanDraft | None,
        entity_extraction_plan: ExtractionPlan,
        entity_candidates: Sequence[CandidateEntity],
        entity_candidate_graph: CandidateMemoryGraph,
        resolved_entity_map: ResolvedEntityMap,
        relationship_plan: RelationshipIngestionPlanDraft,
    ) -> IngestionResult:
        supplemental_plans: list[EntityIngestionPlanDraft] = []
        supplemental_extraction_plans: list[ExtractionPlan] = []
        supplemental_candidates: list[CandidateEntity] = []
        relationship_view = graph_context_views.get("relationship_planning")

        if relationship_plan.missing_entities:
            missing_result = self._resolve_missing_entities_once(
                source=source,
                graph_context_pack=graph_context_pack,
                graph_context_views=graph_context_views,
                reasoning=reasoning,
                entity_plan=entity_plan,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=list(entity_candidates),
                entity_candidate_graph=entity_candidate_graph,
                resolved_entity_map=resolved_entity_map,
                relationship_plan=relationship_plan,
            )
            if isinstance(missing_result, IngestionResult):
                return missing_result
            (
                supplemental_plans,
                supplemental_extraction_plans,
                supplemental_candidates,
                resolved_entity_map,
            ) = missing_result
            if relationship_view is None:
                relationship_view = self.context_renderer.render(
                    graph_context_pack,
                    GraphContextRenderPurpose.RELATIONSHIP_PLANNING,
                )
                graph_context_views["relationship_planning"] = relationship_view
            relationship_plan = self._plan_relationships(
                source,
                reasoning,
                relationship_view,
                resolved_entity_map,
            )
            if isinstance(relationship_plan, IngestionResult):
                return relationship_plan

        all_entity_candidates = [*entity_candidates, *supplemental_candidates]
        if relationship_plan.clarification is not None:
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.NEEDS_CLARIFICATION,
                graph_context_pack=graph_context_pack,
                graph_context_views=graph_context_views,
                reasoning=reasoning,
                entity_plan=entity_plan,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=list(entity_candidates),
                entity_candidate_graph=entity_candidate_graph,
                supplemental_entity_plans=supplemental_plans,
                supplemental_entity_extraction_plans=supplemental_extraction_plans,
                supplemental_entity_candidates=supplemental_candidates,
                resolved_entity_map=resolved_entity_map,
                relationship_plan=relationship_plan,
                clarification=_clarification_from_draft(
                    relationship_plan.clarification
                ),
                metadata={"ingestion_stage": "relationship_planning_clarification"},
            ))
        if relationship_plan.missing_entities:
            candidate_graph = self._assemble_final_candidate_graph(
                source,
                graph_context_pack,
                entity_extraction_plan,
                supplemental_extraction_plans,
                None,
                all_entity_candidates,
            )
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.PLANNED,
                graph_context_pack=graph_context_pack,
                graph_context_views=graph_context_views,
                reasoning=reasoning,
                entity_plan=entity_plan,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=list(entity_candidates),
                entity_candidate_graph=entity_candidate_graph,
                supplemental_entity_plans=supplemental_plans,
                supplemental_entity_extraction_plans=supplemental_extraction_plans,
                supplemental_entity_candidates=supplemental_candidates,
                resolved_entity_map=resolved_entity_map,
                relationship_plan=relationship_plan,
                candidate_graph=candidate_graph,
                metadata={"ingestion_stage": "relationship_missing_entity_blocked"},
            ))

        plan_build = build_relationship_extraction_plan(
            source,
            graph_context_pack,
            relationship_plan,
            resolved_entity_map,
        )
        if plan_build.validation_issues:
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.VALIDATION_FAILED,
                graph_context_pack=graph_context_pack,
                graph_context_views=graph_context_views,
                reasoning=reasoning,
                entity_plan=entity_plan,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=list(entity_candidates),
                entity_candidate_graph=entity_candidate_graph,
                supplemental_entity_plans=supplemental_plans,
                supplemental_entity_extraction_plans=supplemental_extraction_plans,
                supplemental_entity_candidates=supplemental_candidates,
                resolved_entity_map=resolved_entity_map,
                relationship_plan=relationship_plan,
                relationship_extraction_plan=plan_build.extraction_plan,
                validation_errors=plan_build.validation_issues,
                metadata={"ingestion_stage": "relationship_candidate_preparation"},
            ))

        relationship_candidates, extraction_issues = (
            self._extract_relationship_candidates(
                source,
                graph_context_pack,
                plan_build.extraction_plan,
                resolved_entity_map,
            )
        )
        if extraction_issues:
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.VALIDATION_FAILED,
                graph_context_pack=graph_context_pack,
                graph_context_views=graph_context_views,
                reasoning=reasoning,
                entity_plan=entity_plan,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=list(entity_candidates),
                entity_candidate_graph=entity_candidate_graph,
                supplemental_entity_plans=supplemental_plans,
                supplemental_entity_extraction_plans=supplemental_extraction_plans,
                supplemental_entity_candidates=supplemental_candidates,
                resolved_entity_map=resolved_entity_map,
                relationship_plan=relationship_plan,
                relationship_extraction_plan=plan_build.extraction_plan,
                relationship_candidates=relationship_candidates,
                validation_errors=extraction_issues,
                metadata={"ingestion_stage": "relationship_candidate_preparation"},
            ))

        candidate_graph = self._assemble_final_candidate_graph(
            source,
            graph_context_pack,
            entity_extraction_plan,
            supplemental_extraction_plans,
            plan_build.extraction_plan,
            [*all_entity_candidates, *relationship_candidates],
        )
        validation = self.validator.validate_candidate_graph(candidate_graph)
        if not validation.is_valid:
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.VALIDATION_FAILED,
                graph_context_pack=graph_context_pack,
                graph_context_views=graph_context_views,
                reasoning=reasoning,
                entity_plan=entity_plan,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=list(entity_candidates),
                entity_candidate_graph=entity_candidate_graph,
                supplemental_entity_plans=supplemental_plans,
                supplemental_entity_extraction_plans=supplemental_extraction_plans,
                supplemental_entity_candidates=supplemental_candidates,
                resolved_entity_map=resolved_entity_map,
                relationship_plan=relationship_plan,
                relationship_extraction_plan=plan_build.extraction_plan,
                relationship_candidates=relationship_candidates,
                candidate_graph=candidate_graph,
                validation_errors=validation.issues,
                metadata={"ingestion_stage": "candidate_graph_validation"},
            ))

        return self._complete_write(
            source=source,
            graph_context_pack=graph_context_pack,
            graph_context_views=graph_context_views,
            reasoning=reasoning,
            entity_plan=entity_plan,
            entity_extraction_plan=entity_extraction_plan,
            entity_candidates=list(entity_candidates),
            entity_candidate_graph=entity_candidate_graph,
            supplemental_entity_plans=supplemental_plans,
            supplemental_entity_extraction_plans=supplemental_extraction_plans,
            supplemental_entity_candidates=supplemental_candidates,
            resolved_entity_map=resolved_entity_map,
            relationship_plan=relationship_plan,
            relationship_extraction_plan=plan_build.extraction_plan,
            relationship_candidates=relationship_candidates,
            candidate_graph=candidate_graph,
        )

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
            "relationship_plan": relationship_plan,
            "relationship_extraction_plan": relationship_extraction_plan,
            "relationship_candidates": relationship_candidates,
            "candidate_graph": candidate_graph,
        }
        context = _legacy_context_package(source, graph_context_pack)

        if self.resolution_service is None or self.write_plan_builder is None:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.CANDIDATE_READY,
                    **checkpoint_fields,
                    metadata={"ingestion_stage": "candidate_graph_ready"},
                ),
            )

        resolution = self.resolution_service.resolve(candidate_graph, context)
        if resolution.clarification is not None:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.NEEDS_CLARIFICATION,
                    **checkpoint_fields,
                    clarification=resolution.clarification,
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
                        )
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
                        )
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
                )
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

    def _resolve_missing_entities_once(
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
        resolved_entity_map: ResolvedEntityMap,
        relationship_plan: RelationshipIngestionPlanDraft,
    ) -> (
        tuple[
            list[EntityIngestionPlanDraft],
            list[ExtractionPlan],
            list[CandidateEntity],
            ResolvedEntityMap,
        ]
        | IngestionResult
    ):
        missing_view = self.context_renderer.render(
            graph_context_pack,
            GraphContextRenderPurpose.MISSING_ENTITY_PLANNING,
        )
        graph_context_views["missing_entity_planning"] = missing_view
        supplemental_plans: list[EntityIngestionPlanDraft] = []
        supplemental_extraction_plans: list[ExtractionPlan] = []
        supplemental_candidates: list[CandidateEntity] = []

        for missing_entity in relationship_plan.missing_entities:
            missing_plan = self._plan_missing_entity(
                source,
                reasoning,
                missing_view,
                missing_entity,
                resolved_entity_map,
            )
            if isinstance(missing_plan, IngestionResult):
                return missing_plan
            supplemental_plans.append(missing_plan)
            if missing_plan.clarification is not None:
                return self._finish(IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.NEEDS_CLARIFICATION,
                    graph_context_pack=graph_context_pack,
                    graph_context_views=graph_context_views,
                    reasoning=reasoning,
                    entity_plan=entity_plan,
                    entity_extraction_plan=entity_extraction_plan,
                    entity_candidates=entity_candidates,
                    entity_candidate_graph=entity_candidate_graph,
                    supplemental_entity_plans=supplemental_plans,
                    supplemental_entity_extraction_plans=supplemental_extraction_plans,
                    supplemental_entity_candidates=supplemental_candidates,
                    resolved_entity_map=resolved_entity_map,
                    relationship_plan=relationship_plan,
                    clarification=_clarification_from_draft(missing_plan.clarification),
                    metadata={"ingestion_stage": "missing_entity_planning_clarification"},
                ))
            supplemental_plan = _entity_extraction_plan(
                source,
                graph_context_pack,
                missing_plan,
            )
            supplemental_plan.metadata = {
                **supplemental_plan.metadata,
                "schema_layer": "reasoning_first_missing_entity_extraction_plan",
                "missing_entity_ref": missing_entity.missing_ref,
                "needed_for_relationship_ref": missing_entity.needed_for_relationship_ref,
            }
            supplemental_extraction_plans.append(supplemental_plan)
            candidates, extraction_issues = self._extract_entities(
                source,
                graph_context_pack,
                supplemental_plan,
            )
            if extraction_issues:
                return self._finish(IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    graph_context_pack=graph_context_pack,
                    graph_context_views=graph_context_views,
                    reasoning=reasoning,
                    entity_plan=entity_plan,
                    entity_extraction_plan=entity_extraction_plan,
                    entity_candidates=entity_candidates,
                    entity_candidate_graph=entity_candidate_graph,
                    supplemental_entity_plans=supplemental_plans,
                    supplemental_entity_extraction_plans=supplemental_extraction_plans,
                    supplemental_entity_candidates=supplemental_candidates,
                    resolved_entity_map=resolved_entity_map,
                    relationship_plan=relationship_plan,
                    validation_errors=extraction_issues,
                    metadata={"ingestion_stage": "missing_entity_candidate_preparation"},
                ))
            supplemental_graph = self.assembler.assemble(
                source,
                supplemental_plan,
                candidates,
            )
            validation = self.validator.validate_candidate_graph(supplemental_graph)
            if not validation.is_valid:
                return self._finish(IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    graph_context_pack=graph_context_pack,
                    graph_context_views=graph_context_views,
                    reasoning=reasoning,
                    entity_plan=entity_plan,
                    entity_extraction_plan=entity_extraction_plan,
                    entity_candidates=entity_candidates,
                    entity_candidate_graph=entity_candidate_graph,
                    supplemental_entity_plans=supplemental_plans,
                    supplemental_entity_extraction_plans=supplemental_extraction_plans,
                    supplemental_entity_candidates=[
                        *supplemental_candidates,
                        *candidates,
                    ],
                    resolved_entity_map=resolved_entity_map,
                    relationship_plan=relationship_plan,
                    validation_errors=validation.issues,
                    metadata={"ingestion_stage": "missing_entity_validation"},
                ))
            supplemental_candidates.extend(candidates)

        updated_resolved_map = self.entity_resolver.resolve(
            [*entity_candidates, *supplemental_candidates],
            graph_context_pack,
        )
        return (
            supplemental_plans,
            supplemental_extraction_plans,
            supplemental_candidates,
            updated_resolved_map,
        )

    def process_source_with_entity_candidates(
        self,
        source: SourceRecordRef,
        entity_candidates: Sequence[CandidateEntity],
        *,
        graph_context_pack: GraphContextPack | None = None,
    ) -> IngestionResult:
        """Run the relationship wave from predefined entity candidates.

        This is intended for local UAT fixtures and controlled relationship
        planner checks. It does not write to graph storage.
        """

        graph_context_pack = (
            graph_context_pack.model_copy(
                update={"source_id": source.source_id}, deep=True
            )
            if graph_context_pack is not None
            else self.graph_context_builder.build(source)
        )
        reasoning_view = self.context_renderer.render(
            graph_context_pack,
            GraphContextRenderPurpose.REASONING,
        )
        reasoning = self._reason(source, graph_context_pack, reasoning_view)
        if isinstance(reasoning, IngestionResult):
            return reasoning

        entity_extraction_plan = _predefined_entity_extraction_plan(
            source,
            graph_context_pack,
        )
        entity_candidates = [
            _ensure_candidate_source_ref(candidate, source)
            for candidate in entity_candidates
        ]
        entity_candidate_graph = self.assembler.assemble(
            source,
            entity_extraction_plan,
            entity_candidates,
        )
        validation = self.validator.validate_candidate_graph(entity_candidate_graph)
        if not validation.is_valid:
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.VALIDATION_FAILED,
                graph_context_pack=graph_context_pack,
                graph_context_views={"reasoning": reasoning_view},
                reasoning=reasoning,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=list(entity_candidates),
                entity_candidate_graph=entity_candidate_graph,
                validation_errors=validation.issues,
                metadata={"ingestion_stage": "predefined_entity_validation"},
            ))

        resolved_entity_map = self.entity_resolver.resolve(
            entity_candidates,
            graph_context_pack,
        )
        relationship_view = self.context_renderer.render(
            graph_context_pack,
            GraphContextRenderPurpose.RELATIONSHIP_PLANNING,
        )
        relationship_plan = self._plan_relationships(
            source,
            reasoning,
            relationship_view,
            resolved_entity_map,
        )
        if isinstance(relationship_plan, IngestionResult):
            return relationship_plan
        if relationship_plan.clarification is not None:
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.NEEDS_CLARIFICATION,
                graph_context_pack=graph_context_pack,
                graph_context_views={
                    "reasoning": reasoning_view,
                    "relationship_planning": relationship_view,
                },
                reasoning=reasoning,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=list(entity_candidates),
                entity_candidate_graph=entity_candidate_graph,
                resolved_entity_map=resolved_entity_map,
                relationship_plan=relationship_plan,
                clarification=_clarification_from_draft(
                    relationship_plan.clarification
                ),
                metadata={"ingestion_stage": "relationship_planning_clarification"},
            ))
        return self._complete_relationship_candidate_preparation(
            source=source,
            graph_context_pack=graph_context_pack,
            graph_context_views={
                "reasoning": reasoning_view,
                "relationship_planning": relationship_view,
            },
            reasoning=reasoning,
            entity_plan=None,
            entity_extraction_plan=entity_extraction_plan,
            entity_candidates=list(entity_candidates),
            entity_candidate_graph=entity_candidate_graph,
            resolved_entity_map=resolved_entity_map,
            relationship_plan=relationship_plan,
        )

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
        if result.status != "ok" or result.structured_output is None:
            return _structured_step_failure(
                source,
                "reasoning",
                result.assistant_text or "Reasoning checkpoint failed.",
            )
        return IngestionReasoningCheckpointDraft.model_validate(
            result.structured_output
        )

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
    ) -> RelationshipIngestionPlanDraft | IngestionResult:
        context = build_relationship_planning_context(
            source_text=source.raw_text or source.content_ref or "",
            graph_context_view=graph_context_view,
            reasoning=reasoning,
            resolved_entity_map=resolved_entity_map,
            timezone=_timezone(source),
        )
        result = self.planning_service.plan(
            context,
            self._execution_context(source),
            output_schema=RelationshipIngestionPlanDraft,
        )
        if result.status != "ok" or result.structured_output is None:
            return _structured_step_failure(
                source,
                "relationship_planning",
                result.assistant_text or "Relationship planning failed.",
            )
        return RelationshipIngestionPlanDraft.model_validate(result.structured_output)

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
        if result.status != "ok" or result.structured_output is None:
            return _structured_step_failure(
                source,
                "missing_entity_planning",
                result.assistant_text or "Missing-entity planning failed.",
            )
        return EntityIngestionPlanDraft.model_validate(result.structured_output)

    def _extract_entities(
        self,
        source: SourceRecordRef,
        graph_context_pack: GraphContextPack,
        extraction_plan: ExtractionPlan,
    ) -> tuple[list[CandidateEntity], list[ValidationIssue]]:
        candidates: list[CandidateEntity] = []
        issues: list[ValidationIssue] = []
        context = _legacy_context_package(source, graph_context_pack)
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
            extracted = list(extractor.extract(source, task, context))
            for candidate in extracted:
                if isinstance(candidate, CandidateEntity):
                    candidates.append(candidate)
                else:
                    issues.append(
                        ValidationIssue(
                            field_path=f"entity_extraction_plan.tasks[{index}]",
                            message="Entity extraction returned a non-entity candidate.",
                            code="unexpected_ingestion_entity_candidate_type",
                            details={
                                "task_id": task.task_id,
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
        context = _legacy_context_package(source, graph_context_pack)
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
            extracted = normalize_relationship_candidate_refs(
                list(extractor.extract(source, task, context)),
                resolved_entity_map,
            )
            for candidate in extracted:
                if isinstance(candidate, CandidateEntity):
                    issues.append(
                        ValidationIssue(
                            field_path=f"relationship_extraction_plan.tasks[{index}]",
                            message="Relationship extraction returned an entity candidate.",
                            code="unexpected_ingestion_relationship_candidate_type",
                            details={
                                "task_id": task.task_id,
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

    def _find_relationship_extractor(
        self, task: ExtractionTask
    ) -> FocusedExtractor | None:
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

    def _execution_context(
        self, source: SourceRecordRef
    ) -> AgenticToolExecutionContext:
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


def _entity_extraction_plan(
    source: SourceRecordRef,
    graph_context_pack: GraphContextPack,
    entity_plan: EntityIngestionPlanDraft,
) -> ExtractionPlan:
    tasks: list[ExtractionTask] = []
    issues: list[str] = []
    for index, action in enumerate(entity_plan.actions, start=1):
        if action.suggested_entity_type is None:
            issues.append(action.action_ref)
            continue
        task_type = task_type_for_entity_type(action.suggested_entity_type)
        tasks.append(
            ExtractionTask(
                task_type=task_type,
                evidence_text=action.evidence_text,
                source_refs=[source.source_id],
                expected_output="Extract entity candidates only.",
                required_context_refs=list(action.context_refs),
                notes=action.notes or action.goal,
                metadata={
                    "schema_layer": "reasoning_first_entity_extraction",
                    "entity_action_ref": action.action_ref,
                    "entity_action_goal": action.goal,
                    "entity_action_index": index,
                    "suggested_entity_type": str(action.suggested_entity_type),
                    "aliases": list(action.aliases),
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
        clarification=(
            _clarification_from_draft(entity_plan.clarification)
            if entity_plan.clarification is not None
            else None
        ),
        context_gaps=list(entity_plan.context_gaps),
        metadata={
            "schema_layer": "reasoning_first_entity_extraction_plan",
            "skipped_actions_missing_entity_type": issues,
        },
    )


def _predefined_entity_extraction_plan(
    source: SourceRecordRef,
    graph_context_pack: GraphContextPack,
) -> ExtractionPlan:
    return ExtractionPlan(
        source_id=source.source_id,
        context_package_id=graph_context_pack.context_pack_id,
        execution_mode=ExtractionExecutionMode.FOCUSED_EXTRACTION,
        reason="Predefined entity candidates supplied by a local UAT fixture.",
        tasks=[],
        metadata={"schema_layer": "reasoning_first_predefined_entity_candidates"},
    )


def _combined_extraction_plan(
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


def _ensure_candidate_source_ref(
    candidate: CandidateEntity,
    source: SourceRecordRef,
) -> CandidateEntity:
    if candidate.source_refs or candidate.evidence_refs:
        return candidate
    return candidate.model_copy(update={"source_refs": [source.source_id]})


def _legacy_context_package(
    source: SourceRecordRef,
    graph_context_pack: GraphContextPack,
) -> IngestionContextPackage:
    return IngestionContextPackage(
        source_id=source.source_id,
        aliases=dict(graph_context_pack.alias_map),
        entities=[
            entity.model_dump(mode="json", exclude_none=True)
            for entity in graph_context_pack.entities
        ],
        relationships=[
            relationship.model_dump(mode="json", exclude_none=True)
            for relationship in graph_context_pack.relationships
        ],
        notes=list(graph_context_pack.notes),
        metadata={
            "graph_context_pack_id": graph_context_pack.context_pack_id,
            "retrieval_strategy": graph_context_pack.retrieval_strategy,
        },
    )


def _clarification_from_draft(
    draft: ClarificationRequestDraft | None,
) -> ClarificationRequest | None:
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


def _structured_step_failure(
    source: SourceRecordRef,
    stage: str,
    message: str,
) -> IngestionResult:
    return IngestionResult(
        source_id=source.source_id,
        status=IngestionStatus.VALIDATION_FAILED,
        validation_errors=[
            ValidationIssue(
                field_path=stage,
                message=message,
                code=f"ingestion_{stage}_failed",
            ),
        ],
        metadata={"ingestion_stage": stage},
    )


def _timezone(source: SourceRecordRef) -> str:
    return str(source.metadata.get("timezone") or "UTC")


def _write_plan_has_mutations(write_plan) -> bool:
    return any(
        (
            write_plan.nodes_to_create,
            write_plan.nodes_to_update,
            write_plan.relationships_to_create,
            write_plan.relationships_to_update,
            write_plan.claims_to_create,
            write_plan.perceptions_to_create,
            write_plan.relationship_contexts_to_create,
            write_plan.metadata_patches,
        )
    )


def _write_plan_counts(write_plan) -> dict[str, int]:
    return {
        "nodes_to_create": len(write_plan.nodes_to_create),
        "nodes_to_update": len(write_plan.nodes_to_update),
        "relationships_to_create": len(write_plan.relationships_to_create),
        "relationships_to_update": len(write_plan.relationships_to_update),
        "claims_to_create": len(write_plan.claims_to_create),
        "perceptions_to_create": len(write_plan.perceptions_to_create),
        "relationship_contexts_to_create": len(write_plan.relationship_contexts_to_create),
        "metadata_patches": len(write_plan.metadata_patches),
    }


def _validation_issue_summaries(
    issues: Sequence[ValidationIssue],
    *,
    limit: int = 20,
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for issue in issues[:limit]:
        summaries.append(
            {
                key: value
                for key, value in {
                    "code": issue.code,
                    "field_path": issue.field_path,
                    "message": _short_text(issue.message),
                    "details": _compact_issue_details(issue.details),
                }.items()
                if value not in (None, "", {}, [])
            },
        )
    if len(issues) > limit:
        summaries.append({"code": "truncated", "remaining_count": len(issues) - limit})
    return summaries


def _compact_issue_details(details: dict[str, object]) -> dict[str, object]:
    allowed_keys = {
        "label",
        "relationship_type",
        "ref",
        "count",
        "execution_mode",
        "task_id",
        "task_type",
        "candidate_count",
    }
    return {
        key: _short_text(value) if isinstance(value, str) else value
        for key, value in details.items()
        if key in allowed_keys
    }


def _short_text(value: str, *, max_chars: int = 260) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}..."
