"""Local UAT-only ingestion entry points."""

from __future__ import annotations

from collections.abc import Sequence

from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    GraphContextPack,
    IngestionResult,
    SourceRecordRef,
    ValidationIssue,
)
from my_digital_brain.ingestion.contracts import GraphContextRenderPurpose
from my_digital_brain.ingestion.enums import IngestionStatus
from my_digital_brain.ingestion.runtime_helpers import (
    clarification_from_draft as _clarification_from_draft,
    ensure_candidate_source_ref as _ensure_candidate_source_ref,
    predefined_entity_extraction_plan as _predefined_entity_extraction_plan,
)

class IngestionUATMixin:
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

        try:
            resolved_entity_map, resolution = self._resolve_entity_candidates(
                source,
                graph_context_pack,
                entity_candidate_graph,
            )
        except (ValueError, RuntimeError) as exc:
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.VALIDATION_FAILED,
                graph_context_pack=graph_context_pack,
                graph_context_views={"reasoning": reasoning_view},
                reasoning=reasoning,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=list(entity_candidates),
                entity_candidate_graph=entity_candidate_graph,
                validation_errors=[ValidationIssue(
                    field_path="resolution_proposals",
                    message=str(exc),
                    code="resolution_proposal_invalid",
                )],
                metadata={"ingestion_stage": "uat_entity_resolution"},
            ))
        if resolution.clarifications:
            return self._finish(IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.NEEDS_CLARIFICATION,
                graph_context_pack=graph_context_pack,
                graph_context_views={"reasoning": reasoning_view},
                reasoning=reasoning,
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=list(entity_candidates),
                entity_candidate_graph=entity_candidate_graph,
                resolved_entity_map=resolved_entity_map,
                clarification=resolution.clarification,
                clarifications=resolution.clarifications,
                metadata={"ingestion_stage": "uat_entity_resolution_clarification"},
            ))
        memory_result = self._prepare_memory_logs(
            source=source,
            graph_context_pack=graph_context_pack,
            graph_context_views={"reasoning": reasoning_view},
            reasoning=reasoning,
            entity_plan=None,
            entity_extraction_plan=entity_extraction_plan,
            entity_candidates=list(entity_candidates),
            entity_candidate_graph=entity_candidate_graph,
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
                    "entity_extraction_plan": entity_extraction_plan,
                    "entity_candidates": list(entity_candidates),
                    "entity_candidate_graph": entity_candidate_graph,
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
                entity_extraction_plan=entity_extraction_plan,
                entity_candidates=list(entity_candidates),
                entity_candidate_graph=entity_candidate_graph,
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
            entity_plan=None,
            entity_extraction_plan=entity_extraction_plan,
            entity_candidates=list(entity_candidates),
            entity_candidate_graph=entity_candidate_graph,
            resolved_entity_map=resolved_entity_map,
            memory_log_plan=memory_log_plan,
            memory_log_extraction_plan=memory_log_extraction_plan,
            memory_logs=memory_logs,
            entity_packet=entity_packet,
            memory_log_packet=memory_log_packet,
            relationship_plan=relationship_plan,
        )

