"""Contracts for backend-owned questions awaiting a user response."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class QuestionMode(StrEnum):
    """Supported MVP presentation configurations for a user question."""

    FREE_RESPONSE = "free_response"
    CONFIRMATION = "confirmation"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"


class QuestionOptionDTO(BaseModel):
    """One human-readable option supplied for a multiple-choice question."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(
        min_length=1,
        description="Concise user-facing choice label without internal references.",
    )
    description: str | None = Field(
        default=None,
        description="Optional factual detail that helps the user distinguish this choice.",
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
    options: list[QuestionOptionDTO] = Field(
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

