from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from my_digital_brain.agentic import (
    AgenticPlanningService,
    AgenticReasoningService,
    AgenticToolExecutionContext,
    ReasoningCheckpointContext,
    ReasoningPurposeGuidelines,
)
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
    RefinedIngestionResult,
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
from my_digital_brain.ingestion.protocols import FocusedExtractor
from my_digital_brain.ingestion.refined_relationships import (
    build_relationship_extraction_plan,
    normalize_relationship_candidate_refs,
)
from my_digital_brain.ingestion.refined_resolution import (
    DeterministicResolvedEntityMapBuilder,
)
from my_digital_brain.ingestion.validation import IngestionValidator

ExecutionContextFactory = Callable[[SourceRecordRef], AgenticToolExecutionContext]


@dataclass(slots=True)
class RefinedIngestionService:
    """Reasoning-first, entity-first ingestion runtime through relationship planning."""

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
    execution_context_factory: ExecutionContextFactory | None = None

    def process_source(self, source: SourceRecordRef) -> RefinedIngestionResult:
        graph_context_pack = self.graph_context_builder.build(source)
        reasoning_view = self.context_renderer.render(
            graph_context_pack,
            GraphContextRenderPurpose.REASONING,
        )
        reasoning = self._reason(source, graph_context_pack, reasoning_view)
        if isinstance(reasoning, RefinedIngestionResult):
            return reasoning

        entity_view = self.context_renderer.render(
            graph_context_pack,
            GraphContextRenderPurpose.ENTITY_PLANNING,
        )
        entity_plan = self._plan_entities(source, reasoning, entity_view)
        if isinstance(entity_plan, RefinedIngestionResult):
            return entity_plan
        if entity_plan.clarification is not None:
            return RefinedIngestionResult(
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
                metadata={"refined_stage": "entity_planning_clarification"},
            )

        entity_extraction_plan = _entity_extraction_plan(
            source, graph_context_pack, entity_plan
        )
        entity_candidates, extraction_issues = self._extract_entities(
            source,
            graph_context_pack,
            entity_extraction_plan,
        )
        if extraction_issues:
            return RefinedIngestionResult(
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
                metadata={"refined_stage": "entity_candidate_preparation"},
            )

        candidate_graph = self.assembler.assemble(
            source,
            entity_extraction_plan,
            entity_candidates,
        )
        validation = self.validator.validate_candidate_graph(candidate_graph)
        if not validation.is_valid:
            return RefinedIngestionResult(
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
                metadata={"refined_stage": "entity_validation"},
            )

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
        if isinstance(relationship_plan, RefinedIngestionResult):
            return relationship_plan
        if relationship_plan.clarification is not None:
            return RefinedIngestionResult(
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
                metadata={"refined_stage": "relationship_planning_clarification"},
            )

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
    ) -> RefinedIngestionResult:
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
            if isinstance(missing_result, RefinedIngestionResult):
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
            if isinstance(relationship_plan, RefinedIngestionResult):
                return relationship_plan

        all_entity_candidates = [*entity_candidates, *supplemental_candidates]
        if relationship_plan.clarification is not None:
            return RefinedIngestionResult(
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
                metadata={"refined_stage": "relationship_planning_clarification"},
            )
        if relationship_plan.missing_entities:
            candidate_graph = self._assemble_final_candidate_graph(
                source,
                graph_context_pack,
                entity_extraction_plan,
                supplemental_extraction_plans,
                None,
                all_entity_candidates,
            )
            return RefinedIngestionResult(
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
                metadata={"refined_stage": "relationship_missing_entity_blocked"},
            )

        plan_build = build_relationship_extraction_plan(
            source,
            graph_context_pack,
            relationship_plan,
            resolved_entity_map,
        )
        if plan_build.validation_issues:
            return RefinedIngestionResult(
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
                metadata={"refined_stage": "relationship_candidate_preparation"},
            )

        relationship_candidates, extraction_issues = (
            self._extract_relationship_candidates(
                source,
                graph_context_pack,
                plan_build.extraction_plan,
                resolved_entity_map,
            )
        )
        if extraction_issues:
            return RefinedIngestionResult(
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
                metadata={"refined_stage": "relationship_candidate_preparation"},
            )

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
            return RefinedIngestionResult(
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
                metadata={"refined_stage": "candidate_graph_validation"},
            )

        return RefinedIngestionResult(
            source_id=source.source_id,
            status=IngestionStatus.CANDIDATE_READY,
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
            metadata={"refined_stage": "relationship_candidate_prepared"},
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
        | RefinedIngestionResult
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
            if isinstance(missing_plan, RefinedIngestionResult):
                return missing_plan
            supplemental_plans.append(missing_plan)
            if missing_plan.clarification is not None:
                return RefinedIngestionResult(
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
                    metadata={"refined_stage": "missing_entity_planning_clarification"},
                )
            supplemental_plan = _entity_extraction_plan(
                source,
                graph_context_pack,
                missing_plan,
            )
            supplemental_plan.metadata = {
                **supplemental_plan.metadata,
                "schema_layer": "refined_missing_entity_extraction_plan",
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
                return RefinedIngestionResult(
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
                    metadata={"refined_stage": "missing_entity_candidate_preparation"},
                )
            supplemental_graph = self.assembler.assemble(
                source,
                supplemental_plan,
                candidates,
            )
            validation = self.validator.validate_candidate_graph(supplemental_graph)
            if not validation.is_valid:
                return RefinedIngestionResult(
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
                    metadata={"refined_stage": "missing_entity_validation"},
                )
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
    ) -> RefinedIngestionResult:
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
        if isinstance(reasoning, RefinedIngestionResult):
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
            return RefinedIngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.VALIDATION_FAILED,
                graph_context_pack=graph_context_pack,
                graph_context_views={"reasoning": reasoning_view},
                reasoning=reasoning,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=list(entity_candidates),
                entity_candidate_graph=entity_candidate_graph,
                validation_errors=validation.issues,
                metadata={"refined_stage": "predefined_entity_validation"},
            )

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
        if isinstance(relationship_plan, RefinedIngestionResult):
            return relationship_plan
        if relationship_plan.clarification is not None:
            return RefinedIngestionResult(
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
                metadata={"refined_stage": "relationship_planning_clarification"},
            )
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
    ) -> IngestionReasoningCheckpointDraft | RefinedIngestionResult:
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
    ) -> EntityIngestionPlanDraft | RefinedIngestionResult:
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
    ) -> RelationshipIngestionPlanDraft | RefinedIngestionResult:
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
    ) -> EntityIngestionPlanDraft | RefinedIngestionResult:
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
                        code="missing_refined_entity_extractor",
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
                            code="unexpected_refined_entity_candidate_type",
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
                        code="missing_refined_relationship_extractor",
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
                            code="unexpected_refined_relationship_candidate_type",
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
        context.current_text = source.raw_text or source.content_ref
        context.metadata = {
            **context.metadata,
            "source_id": source.source_id,
            "refined_ingestion": True,
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
                    "schema_layer": "refined_entity_extraction",
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
            "schema_layer": "refined_entity_extraction_plan",
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
        metadata={"schema_layer": "refined_predefined_entity_candidates"},
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
        reason="; ".join(reasons) or "Refined ingestion candidate preparation.",
        tasks=tasks,
        context_gaps=context_gaps,
        metadata={
            "schema_layer": "refined_candidate_graph_combined_plan",
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
        aliases={entity.ref: entity.ref for entity in graph_context_pack.entities},
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
        metadata={"schema_layer": "refined_ingestion"},
    )


def _structured_step_failure(
    source: SourceRecordRef,
    stage: str,
    message: str,
) -> RefinedIngestionResult:
    return RefinedIngestionResult(
        source_id=source.source_id,
        status=IngestionStatus.VALIDATION_FAILED,
        validation_errors=[
            ValidationIssue(
                field_path=stage,
                message=message,
                code=f"refined_{stage}_failed",
            ),
        ],
        metadata={"refined_stage": stage},
    )


def _timezone(source: SourceRecordRef) -> str:
    return str(source.metadata.get("timezone") or "UTC")
