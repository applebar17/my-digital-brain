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
    IngestionContextRetriever,
    IngestionPlanner,
    MentionScanner,
)
from my_digital_brain.ingestion.validation import IngestionValidator


@dataclass(slots=True)
class IngestionService:
    """Deterministic Wave 1 ingestion skeleton.

    The service coordinates pluggable scanner, context, planner, and extractor
    components. It does not call LLMs directly and does not execute graph writes.
    """

    scanner: MentionScanner
    context_retriever: IngestionContextRetriever
    planner: IngestionPlanner
    extractors: Sequence[FocusedExtractor] = field(default_factory=list)
    assembler: CandidateGraphAssembler = field(default_factory=CandidateMemoryGraphAssembler)
    validator: IngestionValidator = field(default_factory=IngestionValidator)

    def process_source(self, source: SourceRecordRef) -> IngestionResult:
        mention_scan = self.scanner.scan(source)
        context = self.context_retriever.retrieve(source, mention_scan)
        extraction_plan = self.planner.plan(source, mention_scan, context)

        if (
            extraction_plan.execution_mode
            == ExtractionExecutionMode.NEEDS_CLARIFICATION_FIRST
            and extraction_plan.clarification is not None
        ):
            return IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.NEEDS_CLARIFICATION,
                mention_scan=mention_scan,
                extraction_plan=extraction_plan,
                clarification=extraction_plan.clarification,
            )

        if extraction_plan.execution_mode == ExtractionExecutionMode.NEEDS_CONTEXT_EXPANSION:
            return IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.PLANNED,
                mention_scan=mention_scan,
                extraction_plan=extraction_plan,
                metadata={"reason": "context expansion requested by planner"},
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
            return IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.VALIDATION_FAILED,
                mention_scan=mention_scan,
                extraction_plan=extraction_plan,
                validation_errors=missing_extractor_issues,
            )

        candidate_graph = self.assembler.assemble(source, extraction_plan, candidates)
        validation_result = self.validator.validate_candidate_graph(candidate_graph)
        if not validation_result.is_valid:
            return IngestionResult(
                source_id=source.source_id,
                status=IngestionStatus.VALIDATION_FAILED,
                mention_scan=mention_scan,
                extraction_plan=extraction_plan,
                candidate_graph=candidate_graph,
                validation_errors=validation_result.issues,
            )

        return IngestionResult(
            source_id=source.source_id,
            status=IngestionStatus.CANDIDATE_READY,
            mention_scan=mention_scan,
            extraction_plan=extraction_plan,
            candidate_graph=candidate_graph,
        )

    def _find_extractor(self, task) -> FocusedExtractor | None:
        for extractor in self.extractors:
            if extractor.supports(task):
                return extractor
        return None
