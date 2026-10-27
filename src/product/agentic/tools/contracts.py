"""Model-facing tool definitions and their typed backend handlers."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from product.agentic.tools.models import AgenticToolInvocationContext
from product.ai.ai_clients.protocols.protocol_tools import (
    ToolDefinitionDTO,
    ToolInteractionRequestDTO,
)


@runtime_checkable
class ContextualToolHandler[InputDTO: BaseModel, OutputDTO: BaseModel](Protocol):
    """Handler that consumes backend invocation context as well as model arguments."""

    def invoke_with_context(
        self,
        input_dto: InputDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> OutputDTO | ToolInteractionRequestDTO:
        """Execute using the active parent state and provider call context."""
        ...


@dataclass(frozen=True)
class RegisteredTool[InputDTO: BaseModel, OutputDTO: BaseModel]:
    """Pair one tool definition with the typed handler that implements it."""

    definition: ToolDefinitionDTO[InputDTO]
    handler: (
        Callable[[InputDTO], OutputDTO | ToolInteractionRequestDTO]
        | ContextualToolHandler[InputDTO, OutputDTO]
    )

    def invoke(self, **raw_arguments: object) -> OutputDTO | ToolInteractionRequestDTO:
        """Validate arguments, then return a typed output or external-input request."""
        input_dto = self.definition.input_model.model_validate(raw_arguments)
        if not callable(self.handler):
            raise ValueError(
                f"Tool '{self.definition.name}' requires an active agentic invocation context."
            )
        return self.handler(input_dto)

    def invoke_with_context(
        self,
        invocation_context: AgenticToolInvocationContext,
        **raw_arguments: object,
    ) -> OutputDTO | ToolInteractionRequestDTO:
        """Validate model arguments and invoke contextual handlers with backend metadata."""
        input_dto = self.definition.input_model.model_validate(raw_arguments)
        if isinstance(self.handler, ContextualToolHandler):
            return self.handler.invoke_with_context(input_dto, invocation_context)
        return self.handler(input_dto)
