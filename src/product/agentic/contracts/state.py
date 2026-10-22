"""Typed invocation and result contracts for the reusable agentic state layer."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from product.agentic.contracts.history import PausedStateContinuationDTO
from product.agentic.tools.toolbox import ToolBox
from product.ai.ai_clients.protocols.protocol_chat import Msg
from product.ai.ai_clients.protocols.protocol_tools import ToolCallResultDTO, ToolErrorDTO


class AgenticStateInvocationDTO(BaseModel):
    """Caller-selected context and runtime options for one new state invocation."""

    system_prompt: str = Field(description="Complete system prompt for this state invocation.")
    selected_history: list[Msg] = Field(
        default_factory=list,
        description="History projection selected by the caller; copied into the new state run.",
    )
    request: str = Field(description="One user-role request appended to this state's local history.")
    response_model: type[BaseModel] | None = Field(
        default=None,
        description="Optional Pydantic model requested for the terminal structured output.",
    )
    toolbox: ToolBox | None = Field(
        default=None,
        description="Optional state-specific toolbox of typed definitions and mapped handlers.",
    )
    parallel_tool_calls: bool | None = Field(
        default=None,
        description="Whether the provider may return multiple tool calls in one batch.",
    )
    parent_state_run_id: str | None = Field(
        default=None,
        description="Invoking state run, when this state is called as a child.",
    )
    parent_provider_call_id: str | None = Field(
        default=None,
        description="Provider-issued parent tool-call ID for this child invocation.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class AgenticStateResumeDTO[InteractionDTO: BaseModel](BaseModel):
    """External tool results and runtime toolbox needed to resume one paused state."""

    continuation: PausedStateContinuationDTO[InteractionDTO] = Field(
        description="Paused state transcript and complete provider tool-call batch."
    )
    tool_results: list[ToolCallResultDTO] = Field(
        default_factory=list,
        description="Available results keyed by the original provider call IDs; may be partial.",
    )
    response_model: type[BaseModel] | None = Field(
        default=None,
        description="Same optional structured-output model configured for the original run.",
    )
    toolbox: ToolBox | None = Field(
        default=None,
        description="Toolbox restored by the invoker for the same state configuration.",
    )
    parallel_tool_calls: bool | None = Field(
        default=None,
        description="Provider setting to retain for subsequent tool-call batches.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class AgenticStateResultDTO[InteractionDTO: BaseModel](BaseModel):
    """One state outcome: assistant completion, external-input continuation, or failure."""

    outcome: Literal["completed", "awaiting_input", "failed"] = Field(
        description="Functional outcome of this state invocation or resume operation."
    )
    assistant_message: Msg | None = Field(
        default=None,
        description="Terminal assistant message when the state completed."
    )
    structured_output: BaseModel | None = Field(
        default=None,
        description="Validated terminal artifact when a response model was requested.",
    )
    continuation: PausedStateContinuationDTO[InteractionDTO] | None = Field(
        default=None,
        description="Complete tool-call batch and local transcript when external input is needed.",
    )
    error: ToolErrorDTO | None = Field(
        default=None,
        description="Human-readable runtime failure for the invoking layer."
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)
