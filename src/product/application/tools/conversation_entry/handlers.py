"""Agent-as-tool adaptation for concrete conversation-entry child states."""

from product.agentic.tools import AgenticToolInvocationContext
from product.application.states.memory_query import (
    MemoryQueryRequestDTO,
    MemoryQueryResultDTO,
    MemoryQueryState,
)


class MemoryQueryAgentToolHandler:
    """Invoke `MemoryQueryState` and return only its validated compact result."""

    def __init__(self, state: MemoryQueryState) -> None:
        self.state = state

    def invoke_with_context(
        self,
        request: MemoryQueryRequestDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> MemoryQueryResultDTO:
        """Map one parent tool invocation to one completed child-state artifact.

        Dependencies:
            `MemoryQueryState` owns its internal transcript, initial retrieval,
            iterative tool loop, and structured validation. The parent AI client
            owns provider-call correlation and resumes after this method returns.
        """
        outcome = self.state.query(request, invocation_context)
        if outcome.outcome == "failed":
            message = outcome.error.message if outcome.error is not None else "Unknown state error."
            raise ValueError(f"Memory query state failed: {message}")
        if outcome.outcome != "completed":
            raise ValueError(
                "Memory query state requested external input, but this read-only child state "
                "must complete without a user interaction."
            )
        if not isinstance(outcome.structured_output, MemoryQueryResultDTO):
            raise ValueError("Memory query state completed without its expected result contract.")
        return outcome.structured_output
