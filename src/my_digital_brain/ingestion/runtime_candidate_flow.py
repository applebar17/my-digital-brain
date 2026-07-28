"""Memory and relationship candidate-flow orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

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
)
from my_digital_brain.ingestion.enums import IngestionStatus
from my_digital_brain.ingestion.planning_contexts import (
    build_memory_log_packet,
    build_resolved_entity_packet,
)
from my_digital_brain.ingestion.refined_relationships import build_relationship_extraction_plan
from my_digital_brain.ingestion.runtime_helpers import (
    memory_log_extraction_plan as _memory_log_extraction_plan,
)


class IngestionCandidateFlowMixin:
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
            return self._finish(
                memory_log_plan.model_copy(
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
                )
            )
        memory_log_extraction_plan = _memory_log_extraction_plan(
            source,
            graph_context_pack,
            memory_log_plan,
        )
        memory_extraction = self._extract_memory_logs(
            source,
            graph_context_pack,
            memory_log_view,
            reasoning,
            resolved_entity_map,
            entity_packet,
            memory_log_plan,
            memory_log_extraction_plan,
        )
        if isinstance(memory_extraction, IngestionResult):
            return self._finish(
                memory_extraction.model_copy(
                    update={
                        "graph_context_pack": graph_context_pack,
                        "graph_context_views": graph_context_views,
                        "reasoning": reasoning,
                        "entity_plan": entity_plan,
                        "entity_extraction_plan": entity_extraction_plan,
                        "entity_candidates": list(entity_candidates),
                        "entity_candidate_graph": entity_candidate_graph,
                        "resolved_entity_map": resolved_entity_map,
                        "memory_log_plan": memory_log_plan,
                        "memory_log_extraction_plan": memory_log_extraction_plan,
                    },
                    deep=True,
                )
            )
        memory_logs, extraction_issues = memory_extraction
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
                    entity_candidates=list(entity_candidates),
                    entity_candidate_graph=entity_candidate_graph,
                    resolved_entity_map=resolved_entity_map,
                    memory_log_plan=memory_log_plan,
                    memory_log_extraction_plan=memory_log_extraction_plan,
                    memory_logs=memory_logs,
                    validation_errors=extraction_issues,
                    metadata={"ingestion_stage": "memory_log_candidate_preparation"},
                )
            )

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
            return self._finish(
                IngestionResult(
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
                )
            )

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
        node_resolution: ResolutionResult,
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
                node_resolution,
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
                return self._finish(
                    relationship_plan.model_copy(
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
                    )
                )

        all_entity_candidates = [*entity_candidates, *supplemental_candidates]
        if relationship_plan.missing_entities:
            candidate_graph = self._assemble_final_candidate_graph(
                source,
                graph_context_pack,
                entity_extraction_plan,
                [*supplemental_extraction_plans, memory_log_extraction_plan],
                None,
                [*all_entity_candidates, *memory_logs],
            )
            return self._finish(
                IngestionResult(
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
                )
            )

        plan_build = build_relationship_extraction_plan(
            source,
            graph_context_pack,
            relationship_plan,
            resolved_entity_map,
        )
        if plan_build.validation_issues:
            return self._finish(
                IngestionResult(
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
                )
            )

        relationship_candidates, extraction_issues = self._extract_relationship_candidates(
            source,
            graph_context_pack,
            plan_build.extraction_plan,
            resolved_entity_map,
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
                )
            )

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
            return self._finish(
                IngestionResult(
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
                )
            )

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
            node_resolution=node_resolution,
            memory_log_plan=memory_log_plan,
            memory_log_extraction_plan=memory_log_extraction_plan,
            memory_logs=memory_logs,
            relationship_plan=relationship_plan,
            relationship_extraction_plan=plan_build.extraction_plan,
            relationship_candidates=relationship_candidates,
            candidate_graph=candidate_graph,
        )
