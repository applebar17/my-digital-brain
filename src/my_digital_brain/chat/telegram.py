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
from my_digital_brain.clarification.contracts import ClarificationPacket


class TelegramSendMessage(ChatModel):
    method: str = "sendMessage"
    chat_id: str
    text: str
    reply_to_message_id: int | None = None
    disable_web_page_preview: bool = True
    reply_markup: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TelegramClarificationCallback(ChatModel):
    callback_query_id: str
    chat_id: str
    sender_id: str
    owner_id: str
    message_id: str
    frame_id: str
    question_id: str
    option_id: str
    received_at: datetime
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
        reply_markup = None
        text = response.primary_text
        if response.clarification_packet is not None:
            progress = response.metadata.get("clarification_progress")
            current_question_id = (
                progress.get("current_question_id") if isinstance(progress, dict) else None
            )
            text = self.render_clarification_text(
                response.clarification_packet,
                current_question_id=current_question_id,
            )
            reply_markup = self.render_clarification_reply_markup(
                response.clarification_packet,
                current_question_id=current_question_id,
            )
        return TelegramSendMessage(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=reply_to_message_id,
            reply_markup=reply_markup,
            metadata={
                "response_id": response.response_id,
                "session_id": response.session_id,
                "status": response.status,
            },
        )

    def normalize_callback_query(
        self,
        update: Mapping[str, Any],
    ) -> TelegramClarificationCallback:
        callback = self._as_mapping(update.get("callback_query"), field_name="callback_query")
        sender = self._as_mapping(callback.get("from"), field_name="callback_query.from")
        sender_id = str(self._required(sender, "id", "callback_query.from.id"))
        if self.allowed_user_ids and sender_id not in self.allowed_user_ids:
            raise ChatValidationError(f"Telegram sender is not allowed: {sender_id}")

        message = self._as_mapping(callback.get("message"), field_name="callback_query.message")
        chat = self._as_mapping(message.get("chat"), field_name="callback_query.message.chat")
        chat_id = str(self._required(chat, "id", "callback_query.message.chat.id"))
        message_id = str(
            self._required(
                message,
                "message_id",
                "callback_query.message.message_id",
            ),
        )
        frame_id, question_id, option_id = self._parse_callback_data(
            str(self._required(callback, "data", "callback_query.data")),
        )
        return TelegramClarificationCallback(
            callback_query_id=str(
                self._required(callback, "id", "callback_query.id"),
            ),
            chat_id=chat_id,
            sender_id=sender_id,
            owner_id=sender_id,
            message_id=str(callback.get("id") or message_id),
            frame_id=frame_id,
            question_id=question_id,
            option_id=option_id,
            received_at=self._received_at(message),
            metadata={
                "telegram_update_id": update.get("update_id"),
                "telegram_message_id": message_id,
                "telegram_chat_type": chat.get("type"),
            },
        )

    def is_callback_query(self, update: Mapping[str, Any]) -> bool:
        return isinstance(update.get("callback_query"), Mapping)

    def render_clarification_text(
        self,
        packet: ClarificationPacket,
        *,
        current_question_id: str | None = None,
    ) -> str:
        question = self._current_packet_question(packet, current_question_id)
        lines = [question.question]
        if question.options:
            lines.append("")
            lines.append("Suggested answers:")
            lines.extend(f"- {option.label}" for option in question.options)
        if question.free_text_allowed:
            lines.append("")
            lines.append("You can reply with your own answer.")
        return "\n".join(lines).strip()

    def render_clarification_reply_markup(
        self,
        packet: ClarificationPacket,
        *,
        current_question_id: str | None = None,
    ) -> dict[str, Any] | None:
        question = self._current_packet_question(packet, current_question_id)
        if not question.options:
            return None
        return {
            "inline_keyboard": [
                [
                    {
                        "text": option.label,
                        "callback_data": self._callback_data(
                            packet.frame_id,
                            question.question_id,
                            option.option_id,
                        ),
                    }
                ]
                for option in question.options
            ]
        }

    def _extract_message(self, update: Mapping[str, Any]) -> Mapping[str, Any]:
        message = update.get("message") or update.get("edited_message")
        return self._as_mapping(message, field_name="message")

    def _current_packet_question(
        self,
        packet: ClarificationPacket,
        current_question_id: str | None = None,
    ):
        if current_question_id:
            for question in packet.questions:
                if question.question_id == current_question_id:
                    return question
        return packet.questions[0]

    def _callback_data(self, frame_id: str, question_id: str, option_id: str) -> str:
        return f"clarify:{frame_id}:{question_id}:{option_id}"

    def _parse_callback_data(self, value: str) -> tuple[str, str, str]:
        parts = value.split(":", 3)
        if len(parts) != 4 or parts[0] != "clarify":
            raise ChatValidationError("Telegram callback data is not a clarification answer.")
        _, frame_id, question_id, option_id = parts
        if not frame_id or not question_id or not option_id:
            raise ChatValidationError("Telegram clarification callback data is incomplete.")
        return frame_id, question_id, option_id

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
