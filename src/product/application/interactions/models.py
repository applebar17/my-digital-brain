"""Contracts for backend-owned questions awaiting a user response."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from product.agentic.contracts import PausedStateContinuationDTO, ToolCallResultDTO


class QuestionMode(StrEnum):
    """Supported MVP presentation configurations for a user question."""

    FREE_RESPONSE = "free_response"
    CONFIRMATION = "confirmation"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"


class QuestionOptionRequestDTO(BaseModel):
    """One human-readable choice proposed in model-facing tool arguments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(
        min_length=1,
        description="Concise user-facing choice label without internal references.",
    )
    description: str | None = Field(
        default=None,
        description="Optional factual detail that helps the user distinguish this choice.",
    )


class QuestionOptionDTO(QuestionOptionRequestDTO):
    """One backend-identified choice exposed to a user-facing channel."""

    option_ref: str = Field(
        min_length=1,
        description="Backend-generated identifier used when the client submits this choice.",
    )


class UserQuestionRequestDTO(BaseModel):
    """Question content requested by an LLM-backed state through `ask_user`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    clarification_ref: str = Field(
        min_length=1,
        description=(
            "Descriptive run-scoped reference for the logical doubt, such as "
            "clarify_gabriele_identity; reuse it when retrying the same doubt."
        ),
    )
    question: str = Field(
        min_length=1,
        description="Natural user-facing question with no provider or database details.",
    )
    mode: QuestionMode = Field(
        description=(
            "Presentation mode: free response, confirmation, single choice, or multiple choice."
        )
    )
    options: list[QuestionOptionRequestDTO] = Field(
        default_factory=list,
        description=(
            "Useful choices for single_choice or multiple_choice; omit for free_response "
            "and confirmation."
        ),
    )
class PendingUserQuestionDTO(BaseModel):
    """Backend-created interaction packet exposed to a user-facing channel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    interaction_ref: str = Field(
        min_length=1,
        description="Backend-generated identifier for this concrete interaction attempt.",
    )
    clarification_ref: str = Field(
        min_length=1,
        description="Logical doubt reference supplied by the invoking LLM state.",
    )
    question: str = Field(description="Question rendered to the user.")
    mode: QuestionMode = Field(description="Client presentation configuration.")
    options: list[QuestionOptionDTO] = Field(default_factory=list)
    allow_other: bool = Field(
        description=(
            "Backend-owned instruction to render a free-text Other/correction response "
            "alongside predefined controls."
        )
    )
    deadline: datetime = Field(
        description="Backend-owned deadline after which this interaction resolves as timed out."
    )


class UserQuestionAnswerDTO(BaseModel):
    """One channel-neutral response submitted for a pending user question."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    interaction_ref: str = Field(
        min_length=1,
        description="Backend interaction being answered.",
    )
    selected_option_refs: list[str] = Field(
        default_factory=list,
        description="Backend option references selected through channel controls.",
    )
    text: str | None = Field(
        default=None,
        description="Free response, confirmation text, or Other/correction supplied by the user.",
    )


class UserQuestionResolutionOutcome(StrEnum):
    """Deterministic outcome supplied to the waiting `ask_user` tool call."""

    ANSWERED = "answered"
    TIMED_OUT = "timed_out"


class UserQuestionResolutionDTO(BaseModel):
    """Normalized answer-or-timeout result returned to the clarification LLM."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    clarification_ref: str
    outcome: UserQuestionResolutionOutcome
    answer: str | None = None


class PendingNestedInteractionDTO(BaseModel):
    """In-process product record linking a child pause to its parent tool call."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    interaction: PendingUserQuestionDTO
    child_continuation: PausedStateContinuationDTO[PendingUserQuestionDTO]
    parent_continuation: PausedStateContinuationDTO[PendingUserQuestionDTO] | None = None
    parent_provider_call_id: str | None = None
    claimed: bool = False


class ParentToolResumeDTO(BaseModel):
    """Completed child output and the exact parent continuation it must resume."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    parent_continuation: PausedStateContinuationDTO[PendingUserQuestionDTO]
    tool_result: ToolCallResultDTO

