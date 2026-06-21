from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from my_digital_brain.chat.enums import ChatChannel
from my_digital_brain.chat.models import ChatModel, IncomingChatMessage, IncomingMediaRef, utc_now


class WebChatMessageRequest(ChatModel):
    session_id: str | None = None
    conversation_id: str
    sender_id: str
    owner_id: str
    message_id: str
    text: str | None = None
    media_refs: list[IncomingMediaRef] = Field(default_factory=list)
    reply_to_message_id: str | None = None
    conversation_history_refs: list[str] = Field(default_factory=list)
    received_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WebChatAdapter:
    """Adapter for the product web chat API.

    The web frontend sends a compact transport payload. The adapter is the
    boundary that turns it into the channel-neutral chat contract.
    """

    def normalize(self, request: WebChatMessageRequest) -> IncomingChatMessage:
        return IncomingChatMessage(
            channel=ChatChannel.WEB,
            session_id=request.session_id,
            conversation_id=request.conversation_id,
            sender_id=request.sender_id,
            owner_id=request.owner_id,
            message_id=request.message_id,
            text=request.text,
            media_refs=request.media_refs,
            reply_to_message_id=request.reply_to_message_id,
            conversation_history_refs=request.conversation_history_refs,
            received_at=request.received_at,
            metadata=request.metadata,
        )
