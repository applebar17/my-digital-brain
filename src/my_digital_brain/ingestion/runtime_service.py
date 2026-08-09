from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from my_digital_brain.agentic import (
    AgenticMemoryLogExtractionService,
    AgenticPlanningService,
    AgenticReasoningService,
    AgenticToolExecutionContext,
)
from my_digital_brain.ai.logging import log_event
from my_digital_brain.ai.session import LLMSessionAwaitingTool
from my_digital_brain.ingestion.assembly import CandidateMemoryGraphAssembler
from my_digital_brain.ingestion.candidate_context import (
    BoundedCandidateContextHydrator,
    CandidateContextHydrationError,
)
from my_digital_brain.ingestion.context_rendering import GraphContextPackRendererService
from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    CandidateMemoryGraph,
    EntityIngestionPlanDraft,
    ExtractionPlan,
    GraphContextPack,
    GraphContextRenderPurpose,
    IngestionReasoningCheckpointDraft,
    IngestionResult,
    MemoryLog,
    MemoryLogIngestionPlanDraft,
    RelationshipIngestionPlanDraft,
    ResolutionResult,
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
from my_digital_brain.ingestion.pending import pending_from_session
from my_digital_brain.ingestion.protocols import (
    FocusedExtractor,
    GraphVectorizationService,
    GraphWritePlanBuilder,
    GraphWritePlanExecutor,
    ResolutionProposalAgent,
)
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry
from my_digital_brain.ingestion.resolution_proposals import ResolutionProposalValidationError
from my_digital_brain.ingestion.runtime_candidate_flow import IngestionCandidateFlowMixin
from my_digital_brain.ingestion.runtime_completion import IngestionCompletionMixin
from my_digital_brain.ingestion.runtime_helpers import (
    DEFAULT_EXTRACTION_DRAFT_BATCH_SIZE,
)
from my_digital_brain.ingestion.runtime_helpers import (
    context_package_for_services as _context_package_for_services,
)
from my_digital_brain.ingestion.runtime_helpers import (
    entity_extraction_plan as _entity_extraction_plan,
)
from my_digital_brain.ingestion.runtime_pipeline import IngestionPipelineMixin
from my_digital_brain.ingestion.runtime_stages import (
    IngestionExtractionMixin,
    IngestionPlanningMixin,
)
from my_digital_brain.ingestion.runtime_uat import IngestionUATMixin
from my_digital_brain.ingestion.validation import IngestionValidator

ExecutionContextFactory = Callable[[SourceRecordRef], AgenticToolExecutionContext]
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionService(
    IngestionCompletionMixin,
    IngestionCandidateFlowMixin,
    IngestionPipelineMixin,
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
    identity_lookup_service: DeterministicIdentityLookupService | None = None
    candidate_context_hydrator: BoundedCandidateContextHydrator | None = None
    resolution_agent: ResolutionProposalAgent | None = None
    assembler: CandidateMemoryGraphAssembler = field(default_factory=CandidateMemoryGraphAssembler)
    validator: IngestionValidator = field(default_factory=IngestionValidator)
    write_plan_builder: GraphWritePlanBuilder | None = None
    write_plan_executor: GraphWritePlanExecutor | None = None
    vectorization_service: GraphVectorizationService | None = None
    execute_write_plan: bool = False
    execution_context_factory: ExecutionContextFactory | None = None
    extraction_draft_batch_size: int = DEFAULT_EXTRACTION_DRAFT_BATCH_SIZE

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
        if self.candidate_context_hydrator is not None:
            packets = self.candidate_context_hydrator.hydrate_packets(
                packets,
                registry=registry,
            )
        existing = {
            packet.candidate_ref: packet for packet in graph_context_pack.identity_lookup_packets
        }
        existing.update({packet.candidate_ref: packet for packet in packets})
        graph_context_pack.identity_lookup_packets = list(existing.values())
        graph_context_pack.alias_map = registry.backend_alias_map()
        graph_context_pack.reference_registry_snapshot = registry.snapshot()
        log_event(
            logger,
            "ingestion.identity_lookup.packet_created",
            component="ingestion",
            source_id=source.source_id,
            packet_count=len(graph_context_pack.identity_lookup_packets),
            packet_statuses=[
                str(packet.lookup.status) for packet in graph_context_pack.identity_lookup_packets
            ],
        )

    def _resolve_entity_candidates(
        self,
        source: SourceRecordRef,
        graph_context_pack: GraphContextPack,
        candidate_graph: CandidateMemoryGraph,
    ) -> tuple[ResolvedEntityMap, Any | None] | IngestionResult:
        if self.resolution_agent is None:
            raise ValueError(
                "A structured resolution proposal agent is required for entity resolution."
            )
        context = _context_package_for_services(source, graph_context_pack)
        execution_context = self._execution_context(source)
        resolution_kwargs = {
            "source_text": source.raw_text,
            "context": context,
            "candidate_graph": candidate_graph,
            "packets": graph_context_pack.identity_lookup_packets,
        }
        if execution_context.agentic_runtime is not None:
            resolution_kwargs["execution_context"] = execution_context
        resolution = self.resolution_agent.resolve_nodes(
            **resolution_kwargs,
        )
        if isinstance(resolution, LLMSessionAwaitingTool):
            return IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.PLANNED,
                graph_context_pack=graph_context_pack,
                entity_candidate_graph=candidate_graph,
                pending_interaction=pending_from_session(
                    resolution,
                    stage="entity_resolution",
                ),
                metadata={"ingestion_stage": "entity_resolution"},
            )
        resolved_map, result = resolution
        log_event(
            logger,
            "ingestion.resolution.validation_decision",
            component="ingestion",
            source_id=source.source_id,
            decision_count=len(result.decisions),
            policy=result.metadata.get("policy"),
        )
        return resolved_map, result

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
            ResolutionResult,
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
            try:
                self._attach_identity_lookup_packets(source, graph_context_pack, missing_plan)
            except (IdentityLookupError, CandidateContextHydrationError) as exc:
                return self._finish(
                    IngestionResult(
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
                        validation_errors=[
                            ValidationIssue(
                                field_path="identity_lookup",
                                message=str(exc),
                                code="identity_lookup_failed",
                            )
                        ],
                        metadata={"ingestion_stage": "missing_entity_identity_lookup"},
                    )
                )
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
                return self._finish(
                    IngestionResult(
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
                    )
                )
            supplemental_graph = self.assembler.assemble(
                source,
                supplemental_plan,
                candidates,
            )
            validation = self.validator.validate_candidate_graph(supplemental_graph)
            if not validation.is_valid:
                return self._finish(
                    IngestionResult(
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
                    )
                )
            supplemental_candidates.extend(candidates)

        combined_entity_graph = self._assemble_final_candidate_graph(
            source,
            graph_context_pack,
            entity_extraction_plan,
            supplemental_extraction_plans,
            None,
            [*entity_candidates, *supplemental_candidates],
        )
        try:
            entity_resolution = self._resolve_entity_candidates(
                source,
                graph_context_pack,
                combined_entity_graph,
            )
            if isinstance(entity_resolution, IngestionResult):
                return self._finish(
                    entity_resolution.model_copy(
                        update={
                            "graph_context_pack": graph_context_pack,
                            "graph_context_views": graph_context_views,
                            "reasoning": reasoning,
                            "entity_plan": entity_plan,
                            "entity_extraction_plan": entity_extraction_plan,
                            "entity_candidates": entity_candidates,
                            "entity_candidate_graph": entity_candidate_graph,
                            "supplemental_entity_plans": supplemental_plans,
                            "supplemental_entity_extraction_plans": supplemental_extraction_plans,
                            "supplemental_entity_candidates": supplemental_candidates,
                            "resolved_entity_map": resolved_entity_map,
                            "memory_log_plan": memory_log_plan,
                            "memory_log_extraction_plan": memory_log_extraction_plan,
                            "memory_logs": memory_logs,
                            "relationship_plan": relationship_plan,
                        },
                        deep=True,
                    )
                )
            updated_resolved_map, resolution = entity_resolution
        except (ResolutionProposalValidationError, ValueError) as exc:
            return self._finish(
                IngestionResult(
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
                    validation_errors=[
                        ValidationIssue(
                            field_path="resolution_proposals",
                            message=str(exc),
                            code="resolution_proposal_invalid",
                        ),
                    ],
                    metadata={"ingestion_stage": "missing_entity_resolution"},
                ),
            )
        return (
            supplemental_plans,
            supplemental_extraction_plans,
            supplemental_candidates,
            updated_resolved_map,
            resolution,
        )
