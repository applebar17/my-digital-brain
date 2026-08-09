"""Top-level ingestion pipeline orchestration."""

from __future__ import annotations

import logging
from typing import Any

from my_digital_brain.ai.logging import log_event
from my_digital_brain.ai.session import LLMSessionAwaitingTool
from my_digital_brain.ai.tracing import traceable
from my_digital_brain.ingestion.candidate_context import CandidateContextHydrationError
from my_digital_brain.ingestion.contracts import (
    GraphContextRenderPurpose,
    IngestionResult,
    ResolutionResult,
    SourceRecordRef,
    ValidationIssue,
)
from my_digital_brain.ingestion.enums import IngestionStatus
from my_digital_brain.ingestion.identity_lookup import IdentityLookupError
from my_digital_brain.ingestion.pending import pending_from_session
from my_digital_brain.ingestion.resolution_proposals import ResolutionProposalValidationError
from my_digital_brain.ingestion.runtime_helpers import (
    context_package_for_services as _context_package_for_services,
)
from my_digital_brain.ingestion.runtime_helpers import (
    entity_extraction_plan as _entity_extraction_plan,
)

logger = logging.getLogger(__name__)


class IngestionPipelineMixin:
    def resume_pending(
        self,
        source: SourceRecordRef,
        pending_result: IngestionResult,
        answer_text: str,
    ) -> IngestionResult:
        """Resume a paused stage from its stored LLM session continuation."""

        interaction = pending_result.pending_interaction
        if interaction is None or interaction.continuation is None:
            raise ValueError("The ingestion result does not contain a resumable interaction.")
        if interaction.stage != "entity_resolution":
            raise ValueError(
                f"Ingestion stage '{interaction.stage}' does not support continuation yet."
            )
        if self.resolution_agent is None:
            raise ValueError("A structured resolution proposal agent is required for resumption.")
        if pending_result.graph_context_pack is None:
            raise ValueError("The paused result is missing its graph context checkpoint.")
        if pending_result.entity_candidate_graph is None:
            raise ValueError("The paused result is missing its candidate graph checkpoint.")

        context = _context_package_for_services(source, pending_result.graph_context_pack)
        execution_context = self._execution_context(source)
        try:
            resolution_kwargs = {
                "source_text": source.raw_text,
                "context": context,
                "candidate_graph": pending_result.entity_candidate_graph,
                "packets": pending_result.graph_context_pack.identity_lookup_packets,
                "continuation": interaction.continuation,
                "answer_text": answer_text,
            }
            if execution_context.agentic_runtime is not None:
                resolution_kwargs["execution_context"] = execution_context
            resolution = self.resolution_agent.resume_nodes(**resolution_kwargs)
            if isinstance(resolution, LLMSessionAwaitingTool):
                return self._finish(
                    _checkpoint_result(
                        pending_result,
                        pending_interaction=pending_from_session(
                            resolution,
                            stage="entity_resolution",
                        ),
                    )
                )
            resolved_entity_map, node_resolution = resolution
        except (ResolutionProposalValidationError, ValueError) as exc:
            return self._finish(
                pending_result.model_copy(
                    update={
                        "status": IngestionStatus.VALIDATION_FAILED,
                        "pending_interaction": None,
                        "validation_errors": [
                            ValidationIssue(
                                field_path="resolution_proposals",
                                message=str(exc),
                                code="resolution_proposal_invalid",
                            ),
                        ],
                    },
                    deep=True,
                )
            )

        return self._continue_after_node_resolution(
            source=source,
            graph_context_pack=pending_result.graph_context_pack,
            graph_context_views=dict(pending_result.graph_context_views),
            reasoning=pending_result.reasoning,
            entity_plan=pending_result.entity_plan,
            entity_extraction_plan=pending_result.entity_extraction_plan,
            entity_candidates=pending_result.entity_candidates,
            entity_candidate_graph=pending_result.entity_candidate_graph,
            resolved_entity_map=resolved_entity_map,
            node_resolution=node_resolution,
        )

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
        graph_context_pack = self.graph_context_builder.build(source)
        reasoning_view = self.context_renderer.render(
            graph_context_pack,
            GraphContextRenderPurpose.REASONING,
        )
        reasoning = self._reason(source, graph_context_pack, reasoning_view)
        if isinstance(reasoning, IngestionResult):
            return self._finish(
                reasoning.model_copy(
                    update={
                        "graph_context_pack": graph_context_pack,
                        "graph_context_views": {"reasoning": reasoning_view},
                    },
                    deep=True,
                )
            )

        entity_view = self.context_renderer.render(
            graph_context_pack,
            GraphContextRenderPurpose.ENTITY_PLANNING,
        )
        entity_plan = self._plan_entities(source, reasoning, entity_view)
        if isinstance(entity_plan, IngestionResult):
            return self._finish(
                entity_plan.model_copy(
                    update={
                        "graph_context_pack": graph_context_pack,
                        "graph_context_views": {
                            "reasoning": reasoning_view,
                            "entity_planning": entity_view,
                        },
                        "reasoning": reasoning,
                    },
                    deep=True,
                )
            )
        try:
            self._attach_identity_lookup_packets(source, graph_context_pack, entity_plan)
        except (IdentityLookupError, CandidateContextHydrationError) as exc:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    graph_context_pack=graph_context_pack,
                    graph_context_views={
                        "reasoning": reasoning_view,
                        "entity_planning": entity_view,
                    },
                    reasoning=reasoning,
                    entity_plan=entity_plan,
                    validation_errors=[
                        ValidationIssue(
                            field_path="identity_lookup",
                            message=str(exc),
                            code="identity_lookup_failed",
                        )
                    ],
                    metadata={"ingestion_stage": "identity_lookup"},
                )
            )

        entity_extraction_plan = _entity_extraction_plan(source, graph_context_pack, entity_plan)
        entity_candidates, extraction_issues = self._extract_entities(
            source,
            graph_context_pack,
            entity_extraction_plan,
        )
        if extraction_issues:
            return self._finish(
                IngestionResult(
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
                )
            )

        candidate_graph = self.assembler.assemble(
            source,
            entity_extraction_plan,
            entity_candidates,
        )
        validation = self.validator.validate_candidate_graph(candidate_graph)
        if not validation.is_valid:
            return self._finish(
                IngestionResult(
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
                )
            )

        try:
            resolution = self._resolve_entity_candidates(
                source,
                graph_context_pack,
                candidate_graph,
            )
            if isinstance(resolution, IngestionResult):
                return self._finish(
                    resolution.model_copy(
                        update={
                            "graph_context_pack": graph_context_pack,
                            "graph_context_views": {
                                "reasoning": reasoning_view,
                                "entity_planning": entity_view,
                            },
                            "reasoning": reasoning,
                            "entity_plan": entity_plan,
                            "entity_extraction_plan": entity_extraction_plan,
                            "entity_candidates": entity_candidates,
                            "entity_candidate_graph": candidate_graph,
                        },
                        deep=True,
                    )
                )
            resolved_entity_map, node_resolution = resolution
        except (ResolutionProposalValidationError, ValueError) as exc:
            return self._finish(
                IngestionResult(
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
                    validation_errors=[
                        ValidationIssue(
                            field_path="resolution_proposals",
                            message=str(exc),
                            code="resolution_proposal_invalid",
                        )
                    ],
                    metadata={"ingestion_stage": "entity_resolution_proposals"},
                )
            )
        return self._continue_after_node_resolution(
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
            node_resolution=node_resolution,
        )

    def _continue_after_node_resolution(
        self,
        *,
        source: SourceRecordRef,
        graph_context_pack,
        graph_context_views,
        reasoning,
        entity_plan,
        entity_extraction_plan,
        entity_candidates,
        entity_candidate_graph,
        resolved_entity_map,
        node_resolution: ResolutionResult,
    ) -> IngestionResult:
        memory_result = self._prepare_memory_logs(
            source=source,
            graph_context_pack=graph_context_pack,
            graph_context_views=graph_context_views,
            reasoning=reasoning,
            entity_plan=entity_plan,
            entity_extraction_plan=entity_extraction_plan,
            entity_candidates=entity_candidates,
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
            return self._finish(
                relationship_plan.model_copy(
                    update={
                        "graph_context_pack": graph_context_pack,
                        "graph_context_views": graph_context_views,
                        "reasoning": reasoning,
                        "entity_plan": entity_plan,
                        "entity_extraction_plan": entity_extraction_plan,
                        "entity_candidates": entity_candidates,
                        "entity_candidate_graph": entity_candidate_graph,
                        "resolved_entity_map": resolved_entity_map,
                        "memory_log_plan": memory_log_plan,
                        "memory_log_extraction_plan": memory_log_extraction_plan,
                        "memory_logs": memory_logs,
                    },
                    deep=True,
                )
            )
        return self._complete_relationship_candidate_preparation(
            source=source,
            graph_context_pack=graph_context_pack,
            graph_context_views=graph_context_views,
            reasoning=reasoning,
            entity_plan=entity_plan,
            entity_extraction_plan=entity_extraction_plan,
            entity_candidates=entity_candidates,
            entity_candidate_graph=entity_candidate_graph,
            resolved_entity_map=resolved_entity_map,
            node_resolution=node_resolution,
            memory_log_plan=memory_log_plan,
            memory_log_extraction_plan=memory_log_extraction_plan,
            memory_logs=memory_logs,
            entity_packet=entity_packet,
            memory_log_packet=memory_log_packet,
            relationship_plan=relationship_plan,
        )


def _checkpoint_result(
    result: IngestionResult,
    *,
    pending_interaction: Any,
) -> IngestionResult:
    """Keep every completed pipeline stage while replacing only the continuation."""

    return result.model_copy(
        update={
            "status": IngestionStatus.PLANNED,
            "pending_interaction": pending_interaction,
            "validation_errors": [],
            "metadata": {
                **result.metadata,
                "ingestion_stage": "entity_resolution",
            },
        },
        deep=True,
    )
