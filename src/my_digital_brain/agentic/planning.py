from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from my_digital_brain.agentic.enums import AgenticStateId
from my_digital_brain.agentic.planning_contracts import (
    PlanningTransformContext,
    PlanningTransformResultContext,
)
from my_digital_brain.agentic.runtime import AgenticStateRunner
from my_digital_brain.agentic.runtime_models import AgenticStateInvocation, AgenticStateRunResult
from my_digital_brain.agentic.tools import AgenticToolExecutionContext


@dataclass(slots=True)
class AgenticPlanningService:
    """Reusable entry point for pluggable structured planning states."""

    state_runner: AgenticStateRunner

    def plan(
        self,
        context: PlanningTransformContext,
        execution_context: AgenticToolExecutionContext | None = None,
        *,
        output_schema: type[BaseModel] = PlanningTransformResultContext,
    ) -> AgenticStateRunResult:
        execution_context = execution_context or AgenticToolExecutionContext()
        context = context.model_copy(update={"expected_output_schema": output_schema.__name__})
        return self.state_runner.run_structured_state(
            AgenticStateInvocation(
                state_id=AgenticStateId.PLANNING_CHECKPOINT,
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
