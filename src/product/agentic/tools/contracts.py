"""Model-facing tool definitions and their typed backend handlers."""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from product.ai.ai_clients.protocols.protocol_tools import (
    ToolDefinitionDTO,
    ToolInteractionRequestDTO,
)


@dataclass(frozen=True)
class RegisteredTool[InputDTO: BaseModel, OutputDTO: BaseModel]:
    """Pair one tool definition with the typed handler that implements it."""

    definition: ToolDefinitionDTO[InputDTO]
    handler: Callable[[InputDTO], OutputDTO | ToolInteractionRequestDTO]

    def invoke(self, **raw_arguments: object) -> OutputDTO | ToolInteractionRequestDTO:
        """Validate arguments, then return a typed output or external-input request."""
        input_dto = self.definition.input_model.model_validate(raw_arguments)
        return self.handler(input_dto)
