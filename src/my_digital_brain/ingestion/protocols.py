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
    MentionScan,
    ResolutionDecision,
    SourceRecordRef,
    ValidationResult,
)


@runtime_checkable
class MentionScanner(Protocol):
    def scan(self, source: SourceRecordRef) -> MentionScan:
        """Return cheap mentions from source text before expensive extraction."""


@runtime_checkable
class IngestionContextRetriever(Protocol):
    def retrieve(
        self,
        source: SourceRecordRef,
        mention_scan: MentionScan,
    ) -> IngestionContextPackage:
        """Return compact graph context relevant to the source and mentions."""


@runtime_checkable
class IngestionPlanner(Protocol):
    def plan(
        self,
        source: SourceRecordRef,
        mention_scan: MentionScan,
        context: IngestionContextPackage,
    ) -> ExtractionPlan:
        """Create a backend-executable extraction plan."""


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
    def resolve(self, candidate_graph: CandidateMemoryGraph) -> Sequence[ResolutionDecision]:
        """Resolve candidates against existing graph records."""


@runtime_checkable
class GraphWritePlanExecutor(Protocol):
    def execute(self, write_plan: GraphWritePlan) -> IngestionResult:
        """Apply a validated graph write plan to storage."""
