"""Typed input models for the conversation-entry state."""

from pydantic import BaseModel, ConfigDict, Field


class ConversationEntryRequestDTO(BaseModel):
    """Normalized current user request for top-level conversation routing."""

    model_config = ConfigDict(extra="forbid")

    user_message: str = Field(
        min_length=1,
        description="Current normalized user message to answer directly or route to a capability.",
    )
