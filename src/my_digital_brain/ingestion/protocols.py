from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from my_digital_brain.ingestion.contracts import (
    CandidateMemoryGraph,
    CandidateOutput,
    ExtractionPlan,
    ExtractionTask,
    GraphWritePlan,
    IngestionContextPackage,
    IngestionResult,
    IngestionSessionSnapshot,
    ResolutionResult,
    SourceRecordRef,
    ValidationResult,
)


@runtime_checkable
class FocusedExtractor(Protocol):
    def supports(self, task: ExtractionTask) -> bool:
        """Return whether this extractor can execute the task."""

    def extract(
        self,
        source: SourceRecordRef,
        task: ExtractionTask,
        context: IngestionContextPackage,
    ) -> Sequence[CandidateOutput]:
        """Return candidate records for one focused extraction task."""


@runtime_checkable
class CandidateGraphAssembler(Protocol):
    def assemble(
        self,
        source: SourceRecordRef,
        extraction_plan: ExtractionPlan,
        candidates: Sequence[CandidateOutput],
    ) -> CandidateMemoryGraph:
        """Combine task-level candidates into one candidate memory graph."""


@runtime_checkable
class IngestionValidatorProtocol(Protocol):
    def validate_candidate_graph(self, candidate_graph: CandidateMemoryGraph) -> ValidationResult:
        """Validate candidate refs, labels, relationship types, and evidence."""

    def validate_write_plan(self, write_plan: GraphWritePlan) -> ValidationResult:
        """Validate deterministic graph write commands before execution."""


@runtime_checkable
class ResolutionService(Protocol):
    def resolve(
        self,
        candidate_graph: CandidateMemoryGraph,
        context: IngestionContextPackage | None = None,
    ) -> ResolutionResult:
        """Resolve candidates against existing graph records."""


@runtime_checkable
class GraphWritePlanBuilder(Protocol):
    def build(
        self,
        candidate_graph: CandidateMemoryGraph,
        resolution: ResolutionResult,
        context: IngestionContextPackage | None = None,
    ) -> GraphWritePlan:
        """Build deterministic graph write commands from validated candidates."""


@runtime_checkable
class GraphWritePlanExecutor(Protocol):
    def execute(self, write_plan: GraphWritePlan) -> IngestionResult:
        """Apply a validated graph write plan to storage."""


@runtime_checkable
class GraphVectorizationService(Protocol):
    def vectorize_ingestion_result(self, result: IngestionResult) -> object:
        """Build and store vector records for a successful graph write result."""


@runtime_checkable
class IngestionProcessStore(Protocol):
    def save_source(self, source: SourceRecordRef) -> SourceRecordRef:
        """Persist or remember a source before processing."""

    def record_result(self, result: IngestionResult) -> IngestionSessionSnapshot:
        """Persist or remember the latest ingestion process snapshot."""
