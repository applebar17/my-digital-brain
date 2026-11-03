"""Initial typed slice of the deterministic memory-ingestion workflow."""

from product.agentic.tools import AgenticToolInvocationContext
from product.application.states.ingestion.node_candidate import (
    NodeCandidateSetDTO,
    NodeCandidateState,
    NodeCandidateStateInputDTO,
)
from product.application.states.ingestion.reasoning import (
    IngestionReasoningResultDTO,
    IngestionReasoningState,
)
from product.application.workflows.base import BaseWorkflow, WorkflowContext, WorkflowStep
from product.application.workflows.memory_ingestion.models import (
    IngestionPreparedContextDTO,
    IngestMemoryRequestDTO,
)
from product.application.workflows.memory_ingestion.preparation import IngestionContextPreparer


class IngestionReasoningStepHandler:
    """Adapt prepared workflow context to the linked reasoning child state."""

    def __init__(self, state: IngestionReasoningState) -> None:
        self.state = state

    def invoke_with_context(
        self,
        prepared: IngestionPreparedContextDTO,
        context: WorkflowContext,
    ) -> IngestionReasoningResultDTO:
        """Run reasoning with the workflow's inherited backend invocation context."""
        invocation_context = context.invocation_context
        if invocation_context is None:
            raise ValueError("Ingestion reasoning requires parent invocation context.")
        outcome = self.state.analyze(prepared, invocation_context)
        if outcome.outcome == "failed":
            message = outcome.error.message if outcome.error else "Unknown reasoning failure."
            raise ValueError(f"Ingestion reasoning failed: {message}")
        if outcome.outcome != "completed":
            raise ValueError("Ingestion reasoning must complete without external interaction.")
        if not isinstance(outcome.structured_output, IngestionReasoningResultDTO):
            raise ValueError("Ingestion reasoning returned no validated result contract.")
        return outcome.structured_output


class NodeCandidateStepHandler:
    """Adapt workflow context to the linked node-candidate child state."""

    def __init__(self, state: NodeCandidateState) -> None:
        self.state = state

    def invoke_with_context(
        self,
        state_input: NodeCandidateStateInputDTO,
        context: WorkflowContext,
    ) -> NodeCandidateSetDTO:
        """Run candidate generation with the inherited parent invocation context."""
        invocation_context = context.invocation_context
        if invocation_context is None:
            raise ValueError("Node candidate generation requires parent invocation context.")
        outcome = self.state.generate(state_input, invocation_context)
        if outcome.outcome == "failed":
            message = outcome.error.message if outcome.error else "Unknown candidate failure."
            raise ValueError(f"Node candidate generation failed: {message}")
        if outcome.outcome != "completed":
            raise ValueError("Node candidate generation must complete without external input.")
        if not isinstance(outcome.structured_output, NodeCandidateSetDTO):
            raise ValueError("Node candidate generation returned no validated result contract.")
        return outcome.structured_output


class MemoryIngestionWorkflow(BaseWorkflow):
    """Prepare inherited context and run the read-only ingestion states."""

    WORKFLOW_ID = "memory_ingestion"

    def __init__(
        self,
        preparer: IngestionContextPreparer,
        reasoning_state: IngestionReasoningState,
        candidate_state: NodeCandidateState,
    ) -> None:
        self.preparer = preparer
        self.reasoning_state = reasoning_state
        self.candidate_state = candidate_state
        super().__init__(
            workflow_id=self.WORKFLOW_ID,
            description="Interpret inherited conversation before proposing or writing memory.",
            steps=[
                WorkflowStep(
                    step_id="prepare_context",
                    title="Prepare ingestion context",
                    description="Register owner and retrieve bounded model-safe memory context.",
                    make_input=self._preparation_input,
                    handler=preparer,
                ),
                WorkflowStep(
                    step_id="reason_about_memory",
                    title="Reason about inherited memory",
                    description=(
                        "Identify clarification points and semantic guidance without writing."
                    ),
                    make_input=self._reasoning_input,
                    handler=IngestionReasoningStepHandler(reasoning_state),
                    depends_on=("prepare_context",),
                    kind="agentic",
                    state_id=reasoning_state.state_id,
                ),
                WorkflowStep(
                    step_id="generate_node_candidates",
                    title="Generate semantic node candidates",
                    description=(
                        "Produce explicit typed candidates without lookup or graph writes."
                    ),
                    make_input=self._candidate_input,
                    handler=NodeCandidateStepHandler(candidate_state),
                    depends_on=("prepare_context", "reason_about_memory"),
                    kind="agentic",
                    state_id=candidate_state.state_id,
                ),
            ],
        )

    def run_candidate_slice(
        self,
        request: IngestMemoryRequestDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> NodeCandidateSetDTO:
        """Run preparation, reasoning, and candidate generation without graph writes."""
        results = self.run(request, invocation_context=invocation_context)
        result = results["generate_node_candidates"]
        if not isinstance(result, NodeCandidateSetDTO):
            raise TypeError("Memory-ingestion candidate step returned an unexpected contract.")
        return result

    @staticmethod
    def _preparation_input(context: WorkflowContext) -> IngestMemoryRequestDTO:
        return IngestMemoryRequestDTO.model_validate(context.request)

    @staticmethod
    def _reasoning_input(context: WorkflowContext) -> IngestionPreparedContextDTO:
        return IngestionPreparedContextDTO.model_validate(context.results["prepare_context"])

    @staticmethod
    def _candidate_input(context: WorkflowContext) -> NodeCandidateStateInputDTO:
        prepared = IngestionPreparedContextDTO.model_validate(
            context.results["prepare_context"]
        )
        reasoning = IngestionReasoningResultDTO.model_validate(
            context.results["reason_about_memory"]
        )
        return NodeCandidateStateInputDTO(
            reasoning=reasoning,
            owner=prepared.owner,
            known_references=prepared.known_references,
        )
