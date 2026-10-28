"""Initial typed slice of the deterministic memory-ingestion workflow."""

from product.agentic.tools import AgenticToolInvocationContext
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


class MemoryIngestionWorkflow(BaseWorkflow):
    """Prepare inherited context and run the first non-writing ingestion state."""

    WORKFLOW_ID = "memory_ingestion"

    def __init__(
        self,
        preparer: IngestionContextPreparer,
        reasoning_state: IngestionReasoningState,
    ) -> None:
        self.preparer = preparer
        self.reasoning_state = reasoning_state
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
            ],
        )

    def run_initial_slice(
        self,
        request: IngestMemoryRequestDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> IngestionReasoningResultDTO:
        """Run deterministic preparation and reasoning without claiming ingestion completion."""
        results = self.run(request, invocation_context=invocation_context)
        result = results["reason_about_memory"]
        if not isinstance(result, IngestionReasoningResultDTO):
            raise TypeError("Memory-ingestion reasoning step returned an unexpected contract.")
        return result

    @staticmethod
    def _preparation_input(context: WorkflowContext) -> IngestMemoryRequestDTO:
        return IngestMemoryRequestDTO.model_validate(context.request)

    @staticmethod
    def _reasoning_input(context: WorkflowContext) -> IngestionPreparedContextDTO:
        return IngestionPreparedContextDTO.model_validate(context.results["prepare_context"])
