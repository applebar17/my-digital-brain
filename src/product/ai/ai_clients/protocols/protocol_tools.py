from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, model_validator


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


class ToolInteractionRequestDTO[InteractionDTO: BaseModel](BaseModel):
    """A mapped tool requests external input instead of returning a tool result."""

    interaction_packet: InteractionDTO = Field(
        description="Typed packet to present externally before completing this tool call."
    )


class ToolCallBatchItemDTO[InteractionDTO: BaseModel](BaseModel):
    """One call in an LLM tool batch, represented as output or external input."""

    provider_call_id: str = Field(description="Provider-issued ID for this tool call.")
    tool_name: str = Field(description="Mapped function name returned by the provider.")
    tool_output: ToolOutputDTO | None = Field(
        default=None,
        description="Completed success/error output, absent only while external input is needed.",
    )
    interaction_request: ToolInteractionRequestDTO[InteractionDTO] | None = Field(
        default=None,
        description="External-input request for this call, present until its tool output is supplied.",
    )

    @model_validator(mode="after")
    def validate_one_result_kind(self) -> "ToolCallBatchItemDTO[InteractionDTO]":
        if (self.tool_output is None) == (self.interaction_request is None):
            raise ValueError("A tool batch item must contain exactly one output or interaction request.")
        return self


class ToolCallBatchPauseDTO[InteractionDTO: BaseModel](BaseModel):
    """All results and outstanding interactions for one provider tool-call batch."""

    calls: list[ToolCallBatchItemDTO[InteractionDTO]] = Field(
        description="Every call in original order, with completed outputs and any unanswered interactions."
    )
    tool_calls_processed: int = Field(
        description="Tool-call count already consumed by this client invocation before the pause."
    )
    tool_call_cap: int = Field(
        description="Configured tool-call limit to preserve when this batch resumes."
    )
    seen_call_ids: list[str] = Field(
        description="Provider-issued call IDs already handled in this client invocation."
    )

    @model_validator(mode="after")
    def validate_paused_batch(self) -> "ToolCallBatchPauseDTO[InteractionDTO]":
        call_ids = [call.provider_call_id for call in self.calls]
        if len(call_ids) != len(set(call_ids)):
            raise ValueError("A paused tool batch cannot repeat a provider call ID.")
        if not any(call.interaction_request is not None for call in self.calls):
            raise ValueError("A paused tool batch must contain an unanswered interaction.")
        return self


class ToolCallResultDTO(BaseModel):
    """One externally completed output matched to its original provider call ID."""

    provider_call_id: str = Field(description="Provider-issued call ID being completed.")
    tool_output: ToolOutputDTO = Field(description="Success or error output for that exact call.")
