"""Typed durable-conversation and history-projection contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from product.ai.ai_clients.protocols.protocol_chat import Msg


class ConversationMessageRole(StrEnum):
    """User-visible roles accepted in durable ordinary chat messages."""

    USER = "user"
    ASSISTANT = "assistant"


class ConversationDTO(BaseModel):
    """One durable conversation owned by an application user."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(description="Backend conversation identifier.")
    owner_id: str = Field(description="Application user that owns this conversation.")
    title: str = Field(description="Readable title displayed in conversation lists.")
    created_at: datetime = Field(description="Time at which the conversation was created.")
    updated_at: datetime = Field(description="Time of the latest durable conversation update.")


class CreateConversationCommandDTO(BaseModel):
    """Application request to create one owner-scoped conversation."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None,
        description="Optional initial title; the application may use its normal default.",
    )


class SubmitConversationMessageDTO(BaseModel):
    """One frontend message submission for an existing conversation."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(description="Conversation receiving the new user message.")
    client_message_id: str = Field(
        description="Client-generated idempotency identifier for this user message."
    )
    text: str = Field(min_length=1, description="Current user message to persist and process.")


class AppendConversationMessageCommandDTO(BaseModel):
    """Repository command for one ordinary user-visible message."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(description="Conversation receiving the message.")
    role: ConversationMessageRole = Field(description="Visible author role of the message.")
    text: str = Field(min_length=1, description="Readable message content.")
    client_message_id: str | None = Field(
        default=None,
        description=(
            "Frontend idempotency identifier for user submissions; absent for backend-created "
            "assistant messages."
        ),
    )


class UpsertQuestionAnswerCommandDTO(BaseModel):
    """Repository command that creates a question or attaches its later answer."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(description="Conversation containing the interaction.")
    interaction_ref: str = Field(
        description="Stable application reference joining one question to its answer."
    )
    question: str = Field(min_length=1, description="User-facing question that was presented.")
    answer: str | None = Field(
        default=None,
        description="User answer when received; absent while the interaction is pending.",
    )


class AppendModelContextCommandDTO(BaseModel):
    """Repository command for deliberately promoted context hidden from the frontend."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(description="Conversation receiving the compact context.")
    role: ConversationMessageRole = Field(
        description="Conversation role used when projecting the compact context to the model."
    )
    content: str = Field(
        min_length=1,
        description="Compact readable context selected for later conversation-entry turns.",
    )


class ConversationEntryBaseDTO(BaseModel):
    """Storage-assigned identity and order shared by durable conversation entries."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(description="Backend identifier of this durable conversation entry.")
    conversation_id: str = Field(description="Conversation that owns this entry.")
    sequence: int = Field(ge=1, description="Monotonic order within the conversation.")
    created_at: datetime = Field(description="Time at which this entry was first persisted.")


class ConversationMessageEntryDTO(ConversationEntryBaseDTO):
    """Persisted ordinary message shown in the frontend and supplied to the model."""

    kind: Literal["message"] = "message"
    role: ConversationMessageRole = Field(description="Visible author role of the message.")
    text: str = Field(min_length=1, description="Readable message content.")
    client_message_id: str | None = Field(
        default=None,
        description="Idempotency identifier when this entry came from a frontend submission.",
    )


class QuestionAnswerEntryDTO(ConversationEntryBaseDTO):
    """Persisted user-facing question and its optional answer as one ordered unit."""

    kind: Literal["question_answer"] = "question_answer"
    interaction_ref: str = Field(description="Stable reference joining the question and answer.")
    question: str = Field(min_length=1, description="Question presented to the user.")
    answer: str | None = Field(
        default=None,
        description="Answer received from the user; absent while the interaction is pending.",
    )


class ModelContextEntryDTO(ConversationEntryBaseDTO):
    """Persisted compact context available to the model but hidden from the frontend."""

    kind: Literal["model_context"] = "model_context"
    role: ConversationMessageRole = Field(description="Role used in the model-history projection.")
    content: str = Field(min_length=1, description="Compact model-readable context.")


ConversationEntryDTO = Annotated[
    ConversationMessageEntryDTO | QuestionAnswerEntryDTO | ModelContextEntryDTO,
    Field(discriminator="kind"),
]
FrontendConversationItemDTO = ConversationMessageEntryDTO | QuestionAnswerEntryDTO


class FrontendConversationHistoryDTO(BaseModel):
    """Ordered user-facing conversation page without model-only runtime context."""

    model_config = ConfigDict(extra="forbid")

    items: list[FrontendConversationItemDTO] = Field(
        default_factory=list,
        description="Ordinary messages and readable question/answer interactions.",
    )
    next_before_sequence: int | None = Field(
        default=None,
        description="Sequence cursor for an older page; absent when no older entries remain.",
    )


class ModelHistoryProjectionDTO(BaseModel):
    """Bounded prior conversation messages used to initialize one runtime history session."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    messages: list[Msg] = Field(
        default_factory=list,
        description="Canonical prior messages in model order, excluding the current request.",
    )
