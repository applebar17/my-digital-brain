from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from my_digital_brain.agentic.contexts import (
    ReasoningCheckpointContext,
    ReasoningCheckpointResultContext,
)
from my_digital_brain.agentic.enums import AgenticStateId
from my_digital_brain.agentic.runtime import AgenticStateRunner
from my_digital_brain.agentic.runtime_models import AgenticStateInvocation, AgenticStateRunResult
from my_digital_brain.agentic.tools import AgenticToolExecutionContext


@dataclass(slots=True)
class AgenticReasoningService:
    """Reusable entry point for pluggable reasoning checkpoint states."""

    state_runner: AgenticStateRunner

    def reason(
        self,
        context: ReasoningCheckpointContext,
        execution_context: AgenticToolExecutionContext,
        *,
        output_schema: type[BaseModel] = ReasoningCheckpointResultContext,
    ) -> AgenticStateRunResult:
        context = context.model_copy(update={"expected_output_schema": output_schema.__name__})
        return self.state_runner.run_structured_state(
            AgenticStateInvocation(
                state_id=AgenticStateId.REASONING_CHECKPOINT,
                context_payload=context,
                execution_context=execution_context,
                metadata={
                    "structured_output": True,
                    "output_schema": output_schema.__name__,
                    "purpose_id": context.purpose.purpose_id,
                },
            ),
            output_schema=output_schema,
        )
