from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from my_digital_brain.ai.session import LLMSessionAwaitingTool, LLMSessionContinuation
from my_digital_brain.ingestion.contracts import (
    CandidateMemoryGraph,
    CandidateOutput,
    EntityLookupContextPacket,
    ExtractionPlan,
    ExtractionTask,
    GraphWritePlan,
    IngestionContextPackage,
    IngestionResult,
    ResolutionResult,
    ResolutionStep,
    ResolutionToolAction,
    ResolvedEntityMap,
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
class ResolutionProposalAgent(Protocol):
    def resolve_nodes(
        self,
        *,
        source_text: str | None,
        context: IngestionContextPackage,
        candidate_graph: CandidateMemoryGraph,
        packets: Sequence[EntityLookupContextPacket] = (),
    ) -> tuple[ResolvedEntityMap, ResolutionResult] | LLMSessionAwaitingTool:
        """Collect and validate the complete node proposal set."""

    def propose(
        self,
        *,
        step: ResolutionStep,
        source_text: str | None,
        context: IngestionContextPackage,
        candidate_graph: CandidateMemoryGraph,
        packets: Sequence[EntityLookupContextPacket] = (),
    ) -> list[ResolutionToolAction] | LLMSessionAwaitingTool:
        """Collect proposal actions for one resolution step."""

    def resume_nodes(
        self,
        *,
        source_text: str | None,
        context: IngestionContextPackage,
        candidate_graph: CandidateMemoryGraph,
        packets: Sequence[EntityLookupContextPacket] = (),
        continuation: LLMSessionContinuation,
        answer_text: str,
    ) -> tuple[ResolvedEntityMap, ResolutionResult] | LLMSessionAwaitingTool:
        """Resume node resolution in the same LLM session after clarification."""


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
