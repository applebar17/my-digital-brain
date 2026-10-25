"""Typed models and handler contract for conversation-entry capabilities."""

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field


class ConversationCapabilityRequestDTO(BaseModel):
    """Minimal request forwarded from conversation entry to a child capability."""

    model_config = ConfigDict(extra="forbid")

    request: str = Field(
        min_length=1,
        description="Complete user request that the selected memory capability must handle.",
    )


class ConversationCapabilityResultDTO(BaseModel):
    """Minimal child result returned for interpretation by conversation entry."""

    model_config = ConfigDict(extra="forbid")

    result: str = Field(
        min_length=1,
        description="Readable capability result for the invoking conversation agent to interpret.",
    )


ConversationCapabilityHandler = Callable[
    [ConversationCapabilityRequestDTO], ConversationCapabilityResultDTO
]
