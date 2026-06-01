from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from my_digital_brain.chat.enums import ChatChannel
from my_digital_brain.chat.exceptions import ChatValidationError
from my_digital_brain.chat.models import (
    ChatModel,
    ChatResponse,
    IncomingChatMessage,
    IncomingMediaRef,
)


class TelegramSendMessage(ChatModel):
    method: str = "sendMessage"
    chat_id: str
    text: str
    reply_to_message_id: int | None = None
    disable_web_page_preview: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class TelegramWebhookAdapter:
    """Normalize Telegram webhook updates without leaking Telegram payloads inward."""

    def __init__(self, allowed_user_ids: set[str] | None = None) -> None:
        self.allowed_user_ids = allowed_user_ids or set()

    def normalize_update(self, update: Mapping[str, Any]) -> IncomingChatMessage:
        message = self._extract_message(update)
        sender = self._as_mapping(message.get("from"), field_name="message.from")
        chat = self._as_mapping(message.get("chat"), field_name="message.chat")
        sender_id = str(self._required(sender, "id", "message.from.id"))
        if self.allowed_user_ids and sender_id not in self.allowed_user_ids:
            raise ChatValidationError(f"Telegram sender is not allowed: {sender_id}")

        chat_id = str(self._required(chat, "id", "message.chat.id"))
        message_id = str(self._required(message, "message_id", "message.message_id"))
        text = self._text_from_message(message)
        media_refs = self._media_refs_from_message(message)
        if not text and not media_refs:
            raise ChatValidationError(
                "Telegram update does not contain supported text, caption, voice, or audio.",
            )

        reply_to = message.get("reply_to_message")
        reply_to_message_id = None
        if isinstance(reply_to, Mapping) and reply_to.get("message_id") is not None:
            reply_to_message_id = str(reply_to["message_id"])

        return IncomingChatMessage(
            channel=ChatChannel.TELEGRAM,
            conversation_id=chat_id,
            sender_id=sender_id,
            owner_id=sender_id,
            message_id=message_id,
            text=text,
            media_refs=media_refs,
            reply_to_message_id=reply_to_message_id,
            received_at=self._received_at(message),
            metadata={
                "telegram_update_id": update.get("update_id"),
                "telegram_chat_type": chat.get("type"),
            },
        )

    def render_send_message(
        self,
        response: ChatResponse,
        *,
        chat_id: str,
        reply_to_message_id: int | None = None,
    ) -> TelegramSendMessage:
        return TelegramSendMessage(
            chat_id=chat_id,
            text=response.primary_text,
            reply_to_message_id=reply_to_message_id,
            metadata={
                "response_id": response.response_id,
                "session_id": response.session_id,
                "status": response.status,
            },
        )

    def _extract_message(self, update: Mapping[str, Any]) -> Mapping[str, Any]:
        message = update.get("message") or update.get("edited_message")
        return self._as_mapping(message, field_name="message")

    def _text_from_message(self, message: Mapping[str, Any]) -> str | None:
        value = message.get("text") or message.get("caption")
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _media_refs_from_message(self, message: Mapping[str, Any]) -> list[IncomingMediaRef]:
        refs: list[IncomingMediaRef] = []
        if isinstance(message.get("voice"), Mapping):
            refs.append(self._media_ref("voice", message["voice"]))
        if isinstance(message.get("audio"), Mapping):
            refs.append(self._media_ref("audio", message["audio"]))
        return refs

    def _media_ref(self, media_type: str, payload: Mapping[str, Any]) -> IncomingMediaRef:
        file_id = str(self._required(payload, "file_id", f"{media_type}.file_id"))
        return IncomingMediaRef(
            media_type=media_type,
            storage_ref=f"telegram:file:{file_id}",
            mime_type=payload.get("mime_type"),
            file_name=payload.get("file_name"),
            duration_seconds=payload.get("duration"),
            metadata={
                "telegram_file_id": file_id,
                "telegram_file_unique_id": payload.get("file_unique_id"),
                "file_size": payload.get("file_size"),
            },
        )

    def _received_at(self, message: Mapping[str, Any]) -> datetime:
        timestamp = message.get("date")
        if timestamp is None:
            return datetime.now(timezone.utc)
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc)

    def _required(self, payload: Mapping[str, Any], key: str, path: str) -> Any:
        value = payload.get(key)
        if value is None:
            raise ChatValidationError(f"Telegram payload is missing required field: {path}")
        return value

    def _as_mapping(self, value: Any, *, field_name: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ChatValidationError(f"Telegram payload field must be an object: {field_name}")
        return value
