from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from my_digital_brain.agentic import AgenticRuntime, AgenticStateRunner
from my_digital_brain.ai.schemas import ChatMessage, ProviderCallMetadata
from my_digital_brain.ai.session import (
    LLMCompletionRequest,
    LLMCompletionResult,
    LLMSessionRequest,
    LLMSessionResult,
    LLMSessionRunner,
)
from my_digital_brain.api.routes import telegram as telegram_routes
from my_digital_brain.clarification.interaction import build_clarification_packet
from my_digital_brain.chat.enums import ChatChannel, ChatResponseStatus
from my_digital_brain.chat.models import AgenticFrame, ChatResponse
from my_digital_brain.clarification.contracts import ClarificationPacket
from my_digital_brain.chat.runtime import ChatRuntime
from my_digital_brain.chat.store import InMemoryChatSessionStore
from my_digital_brain.chat.telegram import TelegramWebhookAdapter
from my_digital_brain.chat.web import WebChatAdapter, WebChatMessageRequest
from my_digital_brain.config import Settings


class ScriptedToolProvider:
    provider_name = "scripted"

    def run_session(self, request: LLMSessionRequest) -> LLMSessionResult:
        self._tool_emitted = False
        self._mapping = request.tools_mapping
        return LLMSessionRunner(self).run(request)

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        if not getattr(self, "_tool_emitted", False) and "ingest_memory" in {
            tool["function"]["name"] for tool in request.tools
        }:
            self._tool_emitted = True
            return LLMCompletionResult(
                assistant_message=ChatMessage(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        {
                            "id": "call-ingest",
                            "type": "function",
                            "function": {"name": "ingest_memory", "arguments": "{}"},
                        }
                    ],
                ),
                metadata=ProviderCallMetadata.fake(model=request.model),
            )
        return LLMCompletionResult(
            assistant_message=ChatMessage(
                role="assistant",
                content="accepted:hello from telegram",
            ),
            metadata=ProviderCallMetadata.fake(model=request.model),
        )


def test_web_adapter_normalizes_frontend_payload_to_channel_neutral_message() -> None:
    request = WebChatMessageRequest(
        conversation_id="web-conversation-1",
        sender_id="sender-1",
        owner_id="owner-1",
        message_id="message-1",
        text="remember this",
    )

    normalized = WebChatAdapter().normalize(request)

    assert normalized.channel == ChatChannel.WEB
    assert normalized.conversation_id == "web-conversation-1"
    assert normalized.text == "remember this"


def test_telegram_adapter_normalizes_text_update() -> None:
    normalized = TelegramWebhookAdapter(allowed_user_ids={"42"}).normalize_update(
        _telegram_text_update(text="hello from telegram"),
    )

    assert normalized.channel == ChatChannel.TELEGRAM
    assert normalized.conversation_id == "100"
    assert normalized.sender_id == "42"
    assert normalized.owner_id == "42"
    assert normalized.message_id == "10"
    assert normalized.text == "hello from telegram"


def test_telegram_adapter_normalizes_voice_update_without_text() -> None:
    update = _telegram_text_update(text=None)
    update["message"]["voice"] = {
        "file_id": "voice-file-1",
        "file_unique_id": "voice-unique-1",
        "duration": 12,
        "mime_type": "audio/ogg",
    }

    normalized = TelegramWebhookAdapter().normalize_update(update)

    assert normalized.text is None
    assert normalized.media_refs[0].media_type == "voice"
    assert normalized.media_refs[0].storage_ref == "telegram:file:voice-file-1"
    assert normalized.media_refs[0].duration_seconds == 12


def test_telegram_adapter_renders_clarification_with_inline_buttons() -> None:
    packet = _clarification_packet(frame_id="frame-1")
    response = ChatResponse(
        session_id="session-1",
        status=ChatResponseStatus.AWAITING_CLARIFICATION,
        primary_text="Clarification needed.",
        clarification_packet=packet,
    )

    rendered = TelegramWebhookAdapter().render_send_message(response, chat_id="100")

    assert rendered.text.startswith("Which Marco do you mean?")
    assert "Suggested answers:" in rendered.text
    assert "- Marco from university" in rendered.text
    assert "1." not in rendered.text
    keyboard = rendered.reply_markup["inline_keyboard"]
    assert keyboard[0][0]["text"] == "Marco from university"
    assert keyboard[0][0]["callback_data"] == ("clarify:frame-1:question-1:option-marco-university")


def test_telegram_adapter_renders_plain_clarification_without_options() -> None:
    packet = _clarification_packet(
        frame_id="frame-1",
        questions=[
            {
                "question_id": "question-1",
                "question": "What should I remember?",
                "options": [],
                "free_text_allowed": True,
            }
        ],
    )
    response = ChatResponse(
        session_id="session-1",
        status=ChatResponseStatus.AWAITING_CLARIFICATION,
        primary_text="Clarification needed.",
        clarification_packet=packet,
    )

    rendered = TelegramWebhookAdapter().render_send_message(response, chat_id="100")

    assert rendered.text == "What should I remember?\n\nYou can reply with your own answer."
    assert rendered.reply_markup is None


def test_telegram_webhook_uses_shared_runtime_and_returns_send_message() -> None:
    runtime = ChatRuntime(
        store=InMemoryChatSessionStore(),
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=ScriptedToolProvider())),
    )
    client = _telegram_client(runtime)

    response = client.post(
        "/telegram/webhook",
        json=_telegram_text_update(text="hello from telegram"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
    )

    assert response.status_code == 200
    assert response.json()["method"] == "sendMessage"
    assert response.json()["chat_id"] == "100"
    assert response.json()["text"] == "accepted:hello from telegram"


def test_telegram_webhook_routes_free_text_to_active_clarification() -> None:
    provider = ScriptedToolProvider()
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.TELEGRAM,
        external_conversation_id="100",
        owner_id="42",
    )
    packet = _save_interrupted_frame(
        store,
        session.session_id,
        questions=[
            {
                "question_id": "question-1",
                "question": "What should I remember?",
                "options": [],
                "free_text_allowed": True,
            }
        ],
    )
    runtime = ChatRuntime(
        store=store,
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )
    client = _telegram_client(runtime)

    response = client.post(
        "/telegram/webhook",
        json=_telegram_text_update(text="Marco from Milan."),
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
    )

    assert response.status_code == 200
    assert response.json()["text"] == "accepted:hello from telegram"
    assert store.get_agentic_frame(packet.frame_id).status == "completed"
    messages = runtime.get_session_detail(session.session_id).messages
    answer_message = next(
        message
        for message in messages
        if message.metadata.get("message_kind") == "clarification_answer"
    )
    assert "Marco from Milan." in answer_message.text
    assert (
        answer_message.metadata["clarification_answer_packet"]["answers"][0]["free_text"]
        == "Marco from Milan."
    )


def test_telegram_webhook_routes_callback_to_selected_clarification_option() -> None:
    provider = ScriptedToolProvider()
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.TELEGRAM,
        external_conversation_id="100",
        owner_id="42",
    )
    packet = _save_interrupted_frame(store, session.session_id)
    runtime = ChatRuntime(
        store=store,
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )
    client = _telegram_client(runtime)

    response = client.post(
        "/telegram/webhook",
        json=_telegram_callback_update(
            callback_data="clarify:frame-1:question-1:option-marco-university",
        ),
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
    )

    assert response.status_code == 200
    assert response.json()["text"] == "accepted:hello from telegram"
    answer_message = next(
        message
        for message in runtime.get_session_detail(session.session_id).messages
        if message.metadata.get("message_kind") == "clarification_answer"
    )
    answer = answer_message.metadata["clarification_answer_packet"]["answers"][0]
    assert answer["selected_option_ids"] == ["option-marco-university"]
    assert "free_text" not in answer


def test_telegram_webhook_rejects_free_text_when_clarification_disallows_it() -> None:
    provider = ScriptedToolProvider()
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.TELEGRAM,
        external_conversation_id="100",
        owner_id="42",
    )
    _save_interrupted_frame(
        store,
        session.session_id,
        questions=[
            {
                "question_id": "question-1",
                "question": "Which Marco do you mean?",
                "options": [
                    {
                        "option_id": "option-marco-university",
                        "label": "Marco from university",
                    }
                ],
                "free_text_allowed": False,
            }
        ],
    )
    runtime = ChatRuntime(
        store=store,
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )
    client = _telegram_client(runtime)

    response = client.post(
        "/telegram/webhook",
        json=_telegram_text_update(text="Marco from Milan."),
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
    )

    assert response.status_code == 400
    assert "does not accept free-text" in response.json()["detail"]


def test_telegram_webhook_rejects_missing_secret_and_unknown_sender() -> None:
    runtime = ChatRuntime(
        store=InMemoryChatSessionStore(),
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=ScriptedToolProvider())),
    )
    client = _telegram_client(runtime, allowed_user_ids="999")

    missing_secret = client.post(
        "/telegram/webhook",
        json=_telegram_text_update(text="hello"),
    )
    unknown_sender = client.post(
        "/telegram/webhook",
        json=_telegram_text_update(text="hello"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
    )

    assert missing_secret.status_code == 401
    assert unknown_sender.status_code == 403


def _save_interrupted_frame(
    store: InMemoryChatSessionStore,
    session_id: str,
    *,
    frame_id: str = "frame-1",
    tool_call_id: str = "call-1",
    questions: list[dict[str, object]] | None = None,
) -> ClarificationPacket:
    packet = _clarification_packet(
        frame_id=frame_id,
        tool_call_id=tool_call_id,
        questions=questions,
    )
    store.save_agentic_frame(
        session_id,
        AgenticFrame(
            frame_id=frame_id,
            session_id=session_id,
            state_id="memory_query",
            status="interrupted",
            messages=[
                {"role": "system", "content": "Test system prompt."},
                {"role": "user", "content": "Yesterday I met Marco in Milan."},
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": "ask_clarification",
                                "arguments": "{}",
                            },
                        }
                    ],
                },
            ],
            context_payload={
                "conversation": {
                    "current_message": {
                        "role": "user",
                        "content": "Yesterday I met Marco in Milan.",
                    }
                }
            },
            active_tool_call_id=tool_call_id,
            active_tool_name="ask_clarification",
            clarification_packet=packet,
        ),
    )
    return packet


def _clarification_packet(
    frame_id: str,
    *,
    tool_call_id: str | None = "call-1",
    questions: list[dict[str, object]] | None = None,
) -> ClarificationPacket:
    return build_clarification_packet(
        frame_id=frame_id,
        tool_call_id=tool_call_id,
        tool_name="ask_clarification" if tool_call_id else None,
        origin_state_id="memory_query",
        reason="Multiple Marco candidates exist.",
        target_refs=["NODE_000001", "NODE_000002"],
        questions=questions
        or [
            {
                "question_id": "question-1",
                "question": "Which Marco do you mean?",
                "options": [
                    {
                        "option_id": "option-marco-university",
                        "label": "Marco from university",
                        "recommended": True,
                    },
                    {
                        "option_id": "option-marco-work",
                        "label": "Marco from work",
                    },
                ],
            }
        ],
    )


def _telegram_callback_update(callback_data: str) -> dict[str, object]:
    return {
        "update_id": 2,
        "callback_query": {
            "id": "callback-1",
            "from": {"id": 42, "is_bot": False, "first_name": "Owner"},
            "message": {
                "message_id": 20,
                "date": 1_700_000_001,
                "chat": {"id": 100, "type": "private"},
            },
            "data": callback_data,
        },
    }


def _telegram_text_update(text: str | None) -> dict[str, object]:
    message: dict[str, object] = {
        "message_id": 10,
        "date": 1_700_000_000,
        "chat": {"id": 100, "type": "private"},
        "from": {"id": 42, "is_bot": False, "first_name": "Owner"},
    }
    if text is not None:
        message["text"] = text
    return {"update_id": 1, "message": message}


def _telegram_client(
    runtime: ChatRuntime,
    *,
    allowed_user_ids: str = "42",
) -> TestClient:
    app = FastAPI()
    app.include_router(telegram_routes.router)
    app.dependency_overrides[telegram_routes.get_chat_runtime] = lambda: runtime
    app.dependency_overrides[telegram_routes.get_settings] = lambda: Settings(
        _env_file=None,
        TELEGRAM_WEBHOOK_SECRET_TOKEN="secret",
        TELEGRAM_ALLOWED_USER_IDS=allowed_user_ids,
    )
    return TestClient(app)
