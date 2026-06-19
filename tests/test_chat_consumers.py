from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from my_digital_brain.api.routes import telegram as telegram_routes
from my_digital_brain.agentic import AgenticRuntime, AgenticStateRunner
from my_digital_brain.ai.schemas import ChatRequest, ChatResult, ProviderCallMetadata
from my_digital_brain.ai.tools import ToolBox
from my_digital_brain.chat.enums import ChatChannel, ChatResponseStatus
from my_digital_brain.chat.facade import (
    CancelPendingProcessRequest,
    ChatToolRequest,
    ChatToolResult,
)
from my_digital_brain.chat.runtime import ChatRuntime
from my_digital_brain.chat.store import InMemoryChatSessionStore
from my_digital_brain.chat.telegram import TelegramWebhookAdapter
from my_digital_brain.chat.web import WebChatAdapter, WebChatMessageRequest
from my_digital_brain.config import Settings


class ConsumerFacade:
    def __init__(self) -> None:
        self.last_request: ChatToolRequest | None = None

    def start_memory_ingestion(self, request: ChatToolRequest) -> ChatToolResult:
        self.last_request = request
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text=f"accepted:{request.text or 'media'}",
        )

    def query_memory_context(self, request: ChatToolRequest) -> ChatToolResult:
        self.last_request = request
        return ChatToolResult(primary_text="query accepted")

    def update_memory_graph(self, request: ChatToolRequest) -> ChatToolResult:
        self.last_request = request
        return ChatToolResult(primary_text="graph update accepted")

    def get_conversation_status(self, request: ChatToolRequest) -> ChatToolResult:
        self.last_request = request
        return ChatToolResult(primary_text="status")

    def cancel_pending_process(self, request: CancelPendingProcessRequest) -> ChatToolResult:
        return ChatToolResult(status=ChatResponseStatus.CANCELLED, primary_text="cancelled")


class ScriptedToolProvider:
    provider_name = "scripted"

    def generate_chat_with_tools(
        self,
        request: ChatRequest,
        *,
        toolbox: ToolBox,
        tools_mapping: dict[str, object],
        max_tool_calls: int | None = None,
    ) -> ChatResult:
        if "start_memory_ingestion" in tools_mapping:
            tools_mapping["start_memory_ingestion"](source_text="hello from telegram")
        content = "accepted:hello from telegram"
        return ChatResult(
            content=content,
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


def test_telegram_webhook_uses_shared_runtime_and_returns_send_message() -> None:
    facade = ConsumerFacade()
    runtime = ChatRuntime(
        store=InMemoryChatSessionStore(),
        tool_facade=facade,
        runtime_mode="agentic",
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
    assert facade.last_request is not None
    assert facade.last_request.channel == "telegram"


def test_telegram_webhook_rejects_missing_secret_and_unknown_sender() -> None:
    runtime = ChatRuntime(store=InMemoryChatSessionStore(), tool_facade=ConsumerFacade())
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
