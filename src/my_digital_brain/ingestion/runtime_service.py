from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
import json
import logging
from typing import Any

from my_digital_brain.agentic import (
    AgenticMemoryLogExtractionService,
    AgenticPlanningService,
    AgenticReasoningService,
    AgenticToolExecutionContext,
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
    EntityIngestionPlanDraft,
    ExtractionPlan,
    GraphContextPack,
    GraphContextRenderPurpose,
    IngestionReasoningCheckpointDraft,
    IngestionResult,
    MemoryLog,
    MemoryLogIngestionPlanDraft,
    RelationshipIngestionPlanDraft,
    ResolvedEntityMap,
    SourceRecordRef,
    ValidationIssue,
)
from my_digital_brain.ingestion.enums import IngestionStatus
from my_digital_brain.ingestion.graph_context_pack import (
    WholeSourceGraphContextPackBuilder,
)
from my_digital_brain.ingestion.identity_lookup import (
    DeterministicIdentityLookupService,
    IdentityLookupError,
)
from my_digital_brain.ingestion.planning_contexts import (
    build_memory_log_packet,
    build_resolved_entity_packet,
)
from my_digital_brain.ingestion.protocols import (
    FocusedExtractor,
    GraphVectorizationService,
    GraphWritePlanBuilder,
    GraphWritePlanExecutor,
    IngestionProcessStore,
    ResolutionService,
)
from my_digital_brain.ingestion.refined_relationships import build_relationship_extraction_plan
from my_digital_brain.ingestion.refined_resolution import (
    DeterministicResolvedEntityMapBuilder,
)
from my_digital_brain.ingestion.validation import IngestionValidator
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry
from my_digital_brain.ingestion.runtime_helpers import (
    DEFAULT_EXTRACTION_DRAFT_BATCH_SIZE,
    clarification_from_draft as _clarification_from_draft,
    context_package_for_services as _context_package_for_services,
    entity_extraction_plan as _entity_extraction_plan,
    memory_log_extraction_plan as _memory_log_extraction_plan,
    validation_issue_summaries as _validation_issue_summaries,
    write_plan_counts as _write_plan_counts,
    write_plan_has_mutations as _write_plan_has_mutations,
    batch_sequence as _batch_sequence,
)
from my_digital_brain.ingestion.runtime_stages import (
    IngestionExtractionMixin,
    IngestionPlanningMixin,
)
from my_digital_brain.ingestion.runtime_uat import IngestionUATMixin

ExecutionContextFactory = Callable[[SourceRecordRef], AgenticToolExecutionContext]
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionService(
    IngestionPlanningMixin,
    IngestionExtractionMixin,
    IngestionUATMixin,
):
    """Reasoning-first, entity-first ingestion runtime through durable graph write."""

    reasoning_service: AgenticReasoningService
    planning_service: AgenticPlanningService
    graph_context_builder: WholeSourceGraphContextPackBuilder
    memory_log_extraction_service: AgenticMemoryLogExtractionService | None = None
    entity_extractors: Sequence[FocusedExtractor] = field(default_factory=list)
    relationship_extractors: Sequence[FocusedExtractor] = field(default_factory=list)
    context_renderer: GraphContextPackRendererService = field(
        default_factory=GraphContextPackRendererService,
    )
    entity_resolver: DeterministicResolvedEntityMapBuilder = field(
        default_factory=DeterministicResolvedEntityMapBuilder,
    )
    identity_lookup_service: DeterministicIdentityLookupService | None = None
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
    extraction_draft_batch_size: int = DEFAULT_EXTRACTION_DRAFT_BATCH_SIZE

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

        try:
            self._attach_identity_lookup_packets(source, graph_context_pack, entity_plan)
        except IdentityLookupError as exc:
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
                validation_errors=[ValidationIssue(
                    field_path="identity_lookup",
                    message=str(exc),
                    code="identity_lookup_failed",
                )],
                metadata={"ingestion_stage": "identity_lookup"},
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
            candidate_graph.candidate_entities,
            graph_context_pack,
        )
        memory_result = self._prepare_memory_logs(
            source=source,
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
            resolved_entity_map=resolved_entity_map,
        )
        if isinstance(memory_result, IngestionResult):
            return memory_result
        (
            memory_log_plan,
            memory_log_extraction_plan,
            memory_logs,
            entity_packet,
            memory_log_packet,
            graph_context_views,
        ) = memory_result
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
            entity_packet,
            memory_log_packet,
        )
        if isinstance(relationship_plan, IngestionResult):
            return self._finish(relationship_plan.model_copy(
                update={
                    "graph_context_pack": graph_context_pack,
                    "graph_context_views": graph_context_views,
                    "reasoning": reasoning,
                    "entity_plan": entity_plan,
                    "entity_extraction_plan": entity_extraction_plan,
                    "entity_candidates": entity_candidates,
                    "entity_candidate_graph": candidate_graph,
                    "resolved_entity_map": resolved_entity_map,
                    "memory_log_plan": memory_log_plan,
                    "memory_log_extraction_plan": memory_log_extraction_plan,
                    "memory_logs": memory_logs,
                },
                deep=True,
            ))
        if relationship_plan.clarification is not None:
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.NEEDS_CLARIFICATION,
                graph_context_pack=graph_context_pack,
                graph_context_views=graph_context_views,
                reasoning=reasoning,
                entity_plan=entity_plan,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=entity_candidates,
                entity_candidate_graph=candidate_graph,
                resolved_entity_map=resolved_entity_map,
                memory_log_plan=memory_log_plan,
                memory_log_extraction_plan=memory_log_extraction_plan,
                memory_logs=memory_logs,
                relationship_plan=relationship_plan,
                clarification=_clarification_from_draft(
                    relationship_plan.clarification
                ),
                metadata={"ingestion_stage": "relationship_planning_clarification"},
            ))

        return self._complete_relationship_candidate_preparation(
            source=source,
            graph_context_pack=graph_context_pack,
            graph_context_views=graph_context_views,
            reasoning=reasoning,
            entity_plan=entity_plan,
            entity_extraction_plan=entity_extraction_plan,
            entity_candidates=entity_candidates,
            entity_candidate_graph=candidate_graph,
            resolved_entity_map=resolved_entity_map,
            memory_log_plan=memory_log_plan,
            memory_log_extraction_plan=memory_log_extraction_plan,
            memory_logs=memory_logs,
            entity_packet=entity_packet,
            memory_log_packet=memory_log_packet,
            relationship_plan=relationship_plan,
        )

    def _attach_identity_lookup_packets(
        self,
        source: SourceRecordRef,
        graph_context_pack: GraphContextPack,
        entity_plan: EntityIngestionPlanDraft,
    ) -> None:
        if self.identity_lookup_service is None:
            return
        if not graph_context_pack.reference_registry_snapshot:
            raise IdentityLookupError(
                "Identity lookup requires a Wave 1 reference registry snapshot."
            )
        registry = RunReferenceRegistry.from_snapshot(
            graph_context_pack.reference_registry_snapshot,
        )
        packets = self.identity_lookup_service.lookup_plan(entity_plan, registry=registry)
        existing = {
            packet.candidate_ref: packet
            for packet in graph_context_pack.identity_lookup_packets
        }
        existing.update({packet.candidate_ref: packet for packet in packets})
        graph_context_pack.identity_lookup_packets = list(existing.values())
        graph_context_pack.alias_map = registry.backend_alias_map()
        graph_context_pack.reference_registry_snapshot = registry.snapshot()

    def _prepare_memory_logs(
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
    ) -> (
        tuple[
            MemoryLogIngestionPlanDraft,
            ExtractionPlan,
            list[MemoryLog],
            list[dict[str, Any]],
            list[dict[str, Any]],
            dict[str, Any],
        ]
        | IngestionResult
    ):
        entity_packet = build_resolved_entity_packet(
            list(entity_candidate_graph.candidate_entities),
            resolved_entity_map,
        )
        memory_log_view = self.context_renderer.render(
            graph_context_pack,
            GraphContextRenderPurpose.MEMORY_LOG_PLANNING,
        )
        graph_context_views = {**graph_context_views, "memory_log_planning": memory_log_view}
        memory_log_plan = self._plan_memory_logs(
            source,
            reasoning,
            memory_log_view,
            resolved_entity_map,
            entity_packet,
        )
        if isinstance(memory_log_plan, IngestionResult):
            return self._finish(memory_log_plan.model_copy(
                update={
                    "graph_context_pack": graph_context_pack,
                    "graph_context_views": graph_context_views,
                    "reasoning": reasoning,
                    "entity_plan": entity_plan,
                    "entity_extraction_plan": entity_extraction_plan,
                    "entity_candidates": list(entity_candidates),
                    "entity_candidate_graph": entity_candidate_graph,
                    "resolved_entity_map": resolved_entity_map,
                },
                deep=True,
            ))
        if memory_log_plan.clarification is not None:
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
                resolved_entity_map=resolved_entity_map,
                memory_log_plan=memory_log_plan,
                clarification=_clarification_from_draft(memory_log_plan.clarification),
                metadata={"ingestion_stage": "memory_log_planning_clarification"},
            ))

        memory_log_extraction_plan = _memory_log_extraction_plan(
            source,
            graph_context_pack,
            memory_log_plan,
        )
        memory_logs, extraction_issues, clarification = self._extract_memory_logs(
            source,
            graph_context_pack,
            memory_log_view,
            reasoning,
            resolved_entity_map,
            entity_packet,
            memory_log_plan,
            memory_log_extraction_plan,
        )
        if clarification is not None:
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
                resolved_entity_map=resolved_entity_map,
                memory_log_plan=memory_log_plan,
                memory_log_extraction_plan=memory_log_extraction_plan,
                memory_logs=memory_logs,
                clarification=clarification,
                metadata={"ingestion_stage": "memory_log_extraction_clarification"},
            ))
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
                resolved_entity_map=resolved_entity_map,
                memory_log_plan=memory_log_plan,
                memory_log_extraction_plan=memory_log_extraction_plan,
                memory_logs=memory_logs,
                validation_errors=extraction_issues,
                metadata={"ingestion_stage": "memory_log_candidate_preparation"},
            ))

        candidate_graph = self._assemble_final_candidate_graph(
            source,
            graph_context_pack,
            entity_extraction_plan,
            [memory_log_extraction_plan],
            None,
            [*entity_candidates, *memory_logs],
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
                resolved_entity_map=resolved_entity_map,
                memory_log_plan=memory_log_plan,
                memory_log_extraction_plan=memory_log_extraction_plan,
                memory_logs=memory_logs,
                candidate_graph=candidate_graph,
                validation_errors=validation.issues,
                metadata={"ingestion_stage": "memory_log_validation"},
            ))

        memory_log_packet = build_memory_log_packet(memory_logs)
        return (
            memory_log_plan,
            memory_log_extraction_plan,
            memory_logs,
            entity_packet,
            memory_log_packet,
            graph_context_views,
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
        memory_log_plan: MemoryLogIngestionPlanDraft,
        memory_log_extraction_plan: ExtractionPlan,
        memory_logs: list[MemoryLog],
        entity_packet: list[dict[str, Any]],
        memory_log_packet: list[dict[str, Any]],
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
                memory_log_plan=memory_log_plan,
                memory_log_extraction_plan=memory_log_extraction_plan,
                memory_logs=memory_logs,
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
                build_resolved_entity_packet(
                    [*list(entity_candidates), *supplemental_candidates],
                    resolved_entity_map,
                ),
                memory_log_packet,
            )
            if isinstance(relationship_plan, IngestionResult):
                return self._finish(relationship_plan.model_copy(
                    update={
                        "graph_context_pack": graph_context_pack,
                        "graph_context_views": graph_context_views,
                        "reasoning": reasoning,
                        "entity_plan": entity_plan,
                        "entity_extraction_plan": entity_extraction_plan,
                        "entity_candidates": list(entity_candidates),
                        "entity_candidate_graph": entity_candidate_graph,
                        "supplemental_entity_plans": supplemental_plans,
                        "supplemental_entity_extraction_plans": supplemental_extraction_plans,
                        "supplemental_entity_candidates": supplemental_candidates,
                        "resolved_entity_map": resolved_entity_map,
                        "memory_log_plan": memory_log_plan,
                        "memory_log_extraction_plan": memory_log_extraction_plan,
                        "memory_logs": memory_logs,
                    },
                    deep=True,
                ))

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
                memory_log_plan=memory_log_plan,
                memory_log_extraction_plan=memory_log_extraction_plan,
                memory_logs=memory_logs,
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
                [*supplemental_extraction_plans, memory_log_extraction_plan],
                None,
                [*all_entity_candidates, *memory_logs],
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
                memory_log_plan=memory_log_plan,
                memory_log_extraction_plan=memory_log_extraction_plan,
                memory_logs=memory_logs,
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
                memory_log_plan=memory_log_plan,
                memory_log_extraction_plan=memory_log_extraction_plan,
                memory_logs=memory_logs,
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
                memory_log_plan=memory_log_plan,
                memory_log_extraction_plan=memory_log_extraction_plan,
                memory_logs=memory_logs,
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
            [*supplemental_extraction_plans, memory_log_extraction_plan],
            plan_build.extraction_plan,
            [*all_entity_candidates, *memory_logs, *relationship_candidates],
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
                memory_log_plan=memory_log_plan,
                memory_log_extraction_plan=memory_log_extraction_plan,
                memory_logs=memory_logs,
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
            memory_log_plan=memory_log_plan,
            memory_log_extraction_plan=memory_log_extraction_plan,
            memory_logs=memory_logs,
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
        memory_log_plan: MemoryLogIngestionPlanDraft,
        memory_log_extraction_plan: ExtractionPlan,
        memory_logs: list[MemoryLog],
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
                    memory_log_plan=memory_log_plan,
                    memory_log_extraction_plan=memory_log_extraction_plan,
                    memory_logs=memory_logs,
                    relationship_plan=relationship_plan,
                    clarification=_clarification_from_draft(missing_plan.clarification),
                    metadata={"ingestion_stage": "missing_entity_planning_clarification"},
                ))
            try:
                self._attach_identity_lookup_packets(source, graph_context_pack, missing_plan)
            except IdentityLookupError as exc:
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
                    memory_log_plan=memory_log_plan,
                    memory_log_extraction_plan=memory_log_extraction_plan,
                    memory_logs=memory_logs,
                    relationship_plan=relationship_plan,
                    validation_errors=[ValidationIssue(
                        field_path="identity_lookup",
                        message=str(exc),
                        code="identity_lookup_failed",
                    )],
                    metadata={"ingestion_stage": "missing_entity_identity_lookup"},
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
                    memory_log_plan=memory_log_plan,
                    memory_log_extraction_plan=memory_log_extraction_plan,
                    memory_logs=memory_logs,
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
                    memory_log_plan=memory_log_plan,
                    memory_log_extraction_plan=memory_log_extraction_plan,
                    memory_logs=memory_logs,
                    relationship_plan=relationship_plan,
                    validation_errors=validation.issues,
                    metadata={"ingestion_stage": "missing_entity_validation"},
                ))
            supplemental_candidates.extend(candidates)

        combined_entity_graph = self._assemble_final_candidate_graph(
            source,
            graph_context_pack,
            entity_extraction_plan,
            supplemental_extraction_plans,
            None,
            [*entity_candidates, *supplemental_candidates],
        )
        updated_resolved_map = self.entity_resolver.resolve(
            combined_entity_graph.candidate_entities,
            graph_context_pack,
        )
        return (
            supplemental_plans,
            supplemental_extraction_plans,
            supplemental_candidates,
            updated_resolved_map,
        )
