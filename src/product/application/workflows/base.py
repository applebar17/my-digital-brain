"""Execute declared, typed application steps in dependency order."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from product.agentic.contracts.state import AgenticStateInvocationDTO


@dataclass(frozen=True)
class WorkflowContext:
    """Give an input builder the request and only its declared dependencies."""

    request: BaseModel
    results: Mapping[str, BaseModel]


@dataclass(frozen=True)
class WorkflowStep:
    """One annotated handler and the dependencies that execution and inspection share."""

    step_id: str
    title: str
    description: str
    make_input: Callable[[WorkflowContext], BaseModel]
    handler: Callable[..., BaseModel]
    depends_on: tuple[str, ...] = ()
    kind: Literal["deterministic", "agentic"] = "deterministic"
    state_id: str | None = None
    configuration: AgenticStateInvocationDTO | None = None


class BaseWorkflow:
    """Run explicit step dependencies; expose the same assembled steps to inspection."""

    def __init__(self, workflow_id: str, description: str, steps: Sequence[WorkflowStep]) -> None:
        self.workflow_id = workflow_id
        self.description = description
        self.steps = tuple(steps)
        seen: set[str] = set()
        for step in self.steps:
            if step.step_id in seen:
                raise ValueError(f"Workflow '{workflow_id}' repeats step '{step.step_id}'.")
            missing = set(step.depends_on) - seen
            if missing:
                raise ValueError(
                    f"Step '{step.step_id}' depends on steps not declared before it: "
                    f"{', '.join(sorted(missing))}."
                )
            seen.add(step.step_id)

    def run(self, request: BaseModel) -> dict[str, BaseModel]:
        """Build each typed input from the request and completed declared dependencies."""
        results: dict[str, BaseModel] = {}
        for step in self.steps:
            context = WorkflowContext(
                request=request,
                results={dependency: results[dependency] for dependency in step.depends_on},
            )
            step_input = step.make_input(context)
            results[step.step_id] = step.handler(step_input)
        return results
