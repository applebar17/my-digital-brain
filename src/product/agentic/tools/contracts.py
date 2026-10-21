"""Model-facing tool definitions and their typed backend handlers."""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, Field


class ToolDefinitionDTO[InputDTO: BaseModel](BaseModel):
    """Semantic description of a tool and the DTO accepted from the model."""

    name: str = Field(description="Unique name used to identify this tool in its toolbox.")
    description: str = Field(description="When and why the model should use this tool.")
    input_model: type[InputDTO] = Field(
        description="Pydantic DTO defining and validating the model-provided arguments."
    )


@dataclass
class RegisteredTool[InputDTO: BaseModel, OutputDTO: BaseModel]:
    """Pair one tool definition with the typed handler that implements it."""

    definition: ToolDefinitionDTO[InputDTO]
    handler: Callable[[InputDTO], OutputDTO]
