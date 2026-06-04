from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from my_digital_brain.ingestion.assembly import CandidateMemoryGraphAssembler
from my_digital_brain.ingestion.contracts import (
    CandidateOutput,
    IngestionResult,
    SourceRecordRef,
    ValidationIssue,
)
from my_digital_brain.ingestion.enums import ExtractionExecutionMode, IngestionStatus
from my_digital_brain.ingestion.protocols import (
    CandidateGraphAssembler,
    FocusedExtractor,
    GraphWritePlanBuilder,
    GraphWritePlanExecutor,
    IngestionContextRetriever,
    IngestionPlanner,
    IngestionProcessStore,
    MentionScanner,
    ResolutionService,
)
from my_digital_brain.ingestion.validation import IngestionValidator


@dataclass(slots=True)
class IngestionService:
    """Transport-neutral ingestion orchestrator.

    The service coordinates pluggable scanner, context, planner, and extractor
    components. Graph writes only happen when write-plan components are injected.
    """

    scanner: MentionScanner
    context_retriever: IngestionContextRetriever
    planner: IngestionPlanner
    extractors: Sequence[FocusedExtractor] = field(default_factory=list)
    assembler: CandidateGraphAssembler = field(default_factory=CandidateMemoryGraphAssembler)
    validator: IngestionValidator = field(default_factory=IngestionValidator)
    resolution_service: ResolutionService | None = None
    write_plan_builder: GraphWritePlanBuilder | None = None
    write_plan_executor: GraphWritePlanExecutor | None = None
    execute_write_plan: bool = False
    process_store: IngestionProcessStore | None = None

    def process_source(self, source: SourceRecordRef) -> IngestionResult:
        if self.process_store is not None:
            self.process_store.save_source(source)

        mention_scan = self.scanner.scan(source)
        context = self.context_retriever.retrieve(source, mention_scan)
        extraction_plan = self.planner.plan(source, mention_scan, context)

        if (
            extraction_plan.execution_mode
            == ExtractionExecutionMode.NEEDS_CLARIFICATION_FIRST
            and extraction_plan.clarification is not None
        ):
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.NEEDS_CLARIFICATION,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    clarification=extraction_plan.clarification,
                ),
            )

        if extraction_plan.execution_mode == ExtractionExecutionMode.NEEDS_CONTEXT_EXPANSION:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.PLANNED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    metadata={"reason": "context expansion requested by planner"},
                ),
            )

        if not extraction_plan.tasks:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    validation_errors=[
                        ValidationIssue(
                            field_path="extraction_plan.tasks",
                            message=(
                                "The ingestion planner produced no extraction tasks. "
                                "A memory cannot be stored until at least one focused "
                                "task, clarification, or context-expansion request is "
                                "produced."
                            ),
                            code="empty_extraction_plan",
                            details={
                                "execution_mode": str(extraction_plan.execution_mode),
                            },
                        )
                    ],
                ),
            )

        candidates: list[CandidateOutput] = []
        missing_extractor_issues: list[ValidationIssue] = []
        for task_index, task in enumerate(extraction_plan.tasks):
            extractor = self._find_extractor(task)
            if extractor is None:
                missing_extractor_issues.append(
                    ValidationIssue(
                        field_path=f"extraction_plan.tasks[{task_index}]",
                        message=(
                            f"No focused extractor is registered for task type "
                            f"'{task.task_type}'. Register a backend extractor or "
                            "adjust the planner to avoid this task."
                        ),
                        code="missing_focused_extractor",
                        details={"task_id": task.task_id, "task_type": str(task.task_type)},
                    ),
                )
                continue
            candidates.extend(extractor.extract(source, task, context))

        if missing_extractor_issues:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    validation_errors=missing_extractor_issues,
                ),
            )

        candidate_graph = self.assembler.assemble(source, extraction_plan, candidates)
        if not _candidate_graph_has_outputs(candidate_graph):
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    candidate_graph=candidate_graph,
                    validation_errors=[
                        ValidationIssue(
                            field_path="candidate_graph",
                            message=(
                                "Focused extraction produced no memory candidates. "
                                "No graph write can be executed from an empty candidate "
                                "graph."
                            ),
                            code="empty_candidate_graph",
                            details={
                                "task_count": len(extraction_plan.tasks),
                            },
                        )
                    ],
                ),
            )

        validation_result = self.validator.validate_candidate_graph(candidate_graph)
        if not validation_result.is_valid:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    candidate_graph=candidate_graph,
                    validation_errors=validation_result.issues,
                ),
            )

        if self.resolution_service is None or self.write_plan_builder is None:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.CANDIDATE_READY,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    candidate_graph=candidate_graph,
                ),
            )

        resolution = self.resolution_service.resolve(candidate_graph, context)
        if resolution.clarification is not None:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.NEEDS_CLARIFICATION,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    candidate_graph=candidate_graph,
                    clarification=resolution.clarification,
                ),
            )

        write_plan = self.write_plan_builder.build(candidate_graph, resolution, context)
        if not _write_plan_has_mutations(write_plan):
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    candidate_graph=candidate_graph,
                    write_plan=write_plan,
                    validation_errors=[
                        ValidationIssue(
                            field_path="write_plan",
                            message=(
                                "The resolved write plan contains no graph mutations. "
                                "Memory storage is not considered successful unless at "
                                "least one node, relationship, or patch is written."
                            ),
                            code="empty_write_plan",
                            details={
                                "candidate_count": _candidate_graph_output_count(
                                    candidate_graph,
                                ),
                            },
                        )
                    ],
                ),
            )

        write_validation = self.validator.validate_write_plan(write_plan)
        if not write_validation.is_valid:
            return self._finish(
                IngestionResult(
                    source_id=source.source_id,
                    status=IngestionStatus.VALIDATION_FAILED,
                    mention_scan=mention_scan,
                    extraction_plan=extraction_plan,
                    candidate_graph=candidate_graph,
                    write_plan=write_plan,
                    validation_errors=write_validation.issues,
                ),
            )

        if self.write_plan_executor is not None and self.execute_write_plan:
            result = self.write_plan_executor.execute(write_plan)
            result.mention_scan = mention_scan
            result.extraction_plan = extraction_plan
            result.candidate_graph = candidate_graph
            return self._finish(result)

        return self._finish(
            IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.WRITE_PLAN_READY,
                mention_scan=mention_scan,
                extraction_plan=extraction_plan,
                candidate_graph=candidate_graph,
                write_plan=write_plan,
            ),
        )

    def _find_extractor(self, task) -> FocusedExtractor | None:
        for extractor in self.extractors:
            if extractor.supports(task):
                return extractor
        return None

    def _finish(self, result: IngestionResult) -> IngestionResult:
        if self.process_store is not None:
            self.process_store.record_result(result)
        return result


def _candidate_graph_has_outputs(candidate_graph) -> bool:
    return _candidate_graph_output_count(candidate_graph) > 0


def _candidate_graph_output_count(candidate_graph) -> int:
    return sum(
        len(items)
        for items in (
            candidate_graph.candidate_entities,
            candidate_graph.candidate_relationships,
            candidate_graph.candidate_claims,
            candidate_graph.candidate_perceptions,
            candidate_graph.candidate_relationship_contexts,
            candidate_graph.candidate_metadata_patches,
        )
    )


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
