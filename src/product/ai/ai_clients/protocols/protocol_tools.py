from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class ToolDefinitionDTO[InputDTO: BaseModel](BaseModel):
    """Framework contract describing one model-callable function and its input DTO."""

    name: str = Field(description="Unique function name exposed to the model.")
    description: str = Field(description="When and why the model should call this function.")
    input_model: type[InputDTO] = Field(
        description="Pydantic DTO defining and validating the function arguments."
    )


class ToolErrorDTO(BaseModel):
    """Error information returned as the result of one provider tool call."""

    code: str
    message: str
    hint: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ToolOutputDTO(BaseModel):
    """Normalized tool handler result returned to the calling model."""

    status: Literal["ok", "error"]
    data: Optional[Dict[str, Any]] = None
    error: Optional[ToolErrorDTO] = None
