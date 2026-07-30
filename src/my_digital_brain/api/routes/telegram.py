from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from my_digital_brain.api.routes.chat import chat_http_error, get_chat_runtime
from my_digital_brain.chat.exceptions import ChatValidationError
from my_digital_brain.chat.enums import ChatChannel
from my_digital_brain.chat.models import ChatResponse, IncomingChatMessage
from my_digital_brain.chat.runtime import ChatRuntime
from my_digital_brain.chat.telegram import TelegramSendMessage, TelegramWebhookAdapter
from my_digital_brain.config import Settings, get_settings

router = APIRouter(prefix="/telegram", tags=["telegram"])


def require_telegram_webhook_secret(
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = settings.telegram_webhook_secret_token
    if expected is None:
        return
    if x_telegram_bot_api_secret_token is None:
        raise HTTPException(status_code=401, detail="Missing Telegram webhook secret token.")
    if x_telegram_bot_api_secret_token != expected:
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret token.")


def get_telegram_adapter(settings: Settings = Depends(get_settings)) -> TelegramWebhookAdapter:
    return TelegramWebhookAdapter(allowed_user_ids=settings.telegram_allowed_user_id_set)


@router.post(
    "/webhook",
    response_model=TelegramSendMessage,
    dependencies=[Depends(require_telegram_webhook_secret)],
)
def receive_telegram_webhook(
    update: dict[str, Any],
    runtime: ChatRuntime = Depends(get_chat_runtime),
    adapter: TelegramWebhookAdapter = Depends(get_telegram_adapter),
) -> TelegramSendMessage:
    try:
        if adapter.is_callback_query(update):
            callback = adapter.normalize_callback_query(update)
            message = IncomingChatMessage(
                channel=ChatChannel.TELEGRAM,
                conversation_id=callback.chat_id,
                sender_id=callback.sender_id,
                owner_id=callback.owner_id,
                message_id=callback.message_id,
                received_at=callback.received_at,
                metadata=callback.metadata,
            )
            response = runtime.answer_active_clarification(
                message,
                selected_option_id=callback.option_id,
                expected_frame_id=callback.frame_id,
                expected_question_id=callback.question_id,
            )
            return adapter.render_send_message(response, chat_id=callback.chat_id)

        message = adapter.normalize_update(update)
        _, active_frame = runtime.active_clarification_frame_for_message(message)
        if active_frame is not None and (message.text or message.media_refs):
            response = runtime.answer_active_clarification(
                message,
                text=message.text,
                audio_media_ref=(
                    message.media_refs[0].storage_ref
                    if message.media_refs
                    else None
                ),
            )
        else:
            response = runtime.handle_message(message)
        reply_to_message_id = int(message.message_id) if message.message_id.isdigit() else None
        return adapter.render_send_message(
            response,
            chat_id=message.conversation_id,
            reply_to_message_id=reply_to_message_id,
        )
    except ChatValidationError as exc:
        if "not allowed" in str(exc):
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        raise chat_http_error(exc) from exc
    except Exception as exc:
        raise chat_http_error(exc) from exc
