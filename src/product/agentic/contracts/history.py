"""DTOs for shared master history and one state invocation."""

from pydantic import BaseModel, Field

from product.ai.ai_clients.protocols.protocol_chat import Msg


class StateHistory(BaseModel):
    """State-local transcript and the run linkage that owns its lifecycle."""

    state_id: str = Field(description="Stable identifier of the configured state.")
    state_run_id: str = Field(description="Unique identifier for this state invocation.")
    parent_state_run_id: str | None = Field(
        default=None,
        description="Direct invoking state run, when this invocation is nested.",
    )
    parent_provider_call_id: str | None = Field(
        default=None,
        description="Provider-issued parent tool-call ID, when invoked as a tool.",
    )
    master_history_revision: int = Field(
        description="Shared-history revision selected when this state run began."
    )
    messages: list[Msg] = Field(
        default_factory=list,
        description="This state's owned client transcript, initialized from its selected projection.",
    )


class MasterHistoryPromotion(BaseModel):
    """Record which state run explicitly added messages to shared history."""

    origin_state_run_id: str = Field(description="State run that selected the promoted messages.")
    revision: int = Field(description="New master-history revision after promotion.")
    message_count: int = Field(description="Number of messages added in this promotion.")
