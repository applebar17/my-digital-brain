from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from my_digital_brain.api.routes import chat as chat_routes
from my_digital_brain.chat.enums import (
    ChatChannel,
    ChatResponseStatus,
    PendingProcessKind,
)
from my_digital_brain.chat.facade import (
    CancelPendingProcessRequest,
    ChatToolRequest,
    ChatToolResult,
)
from my_digital_brain.chat.models import (
    ChatResponse,
    ConversationMessage,
    IncomingChatMessage,
    PendingProcessRef,
)
from my_digital_brain.chat.runtime import ChatRuntime
from my_digital_brain.chat.store import InMemoryChatSessionStore
from my_digital_brain.config import Settings


class RecordingFacade:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def start_memory_ingestion(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("start_memory_ingestion", request))
        if request.text == "needs clarification":
            return ChatToolResult(
                status=ChatResponseStatus.NEEDS_USER_INPUT,
                primary_text="Which Marco do you mean?",
                pending_process=PendingProcessRef(
                    process_id="process-1",
                    kind=PendingProcessKind.MEMORY_INGESTION,
                    question="Which Marco do you mean?",
                ),
            )
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="Memory accepted.",
        )

    def query_memory_context(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("query_memory_context", request))
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="Query accepted.",
        )

    def propose_memory_correction(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("propose_memory_correction", request))
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="Correction accepted.",
        )

    def get_conversation_status(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("get_conversation_status", request))
        return ChatToolResult(status=ChatResponseStatus.OK, primary_text="Status checked.")

    def cancel_pending_process(self, request: CancelPendingProcessRequest) -> ChatToolResult:
        self.calls.append(("cancel_pending_process", request))
        return ChatToolResult(
            status=ChatResponseStatus.CANCELLED,
            primary_text="Cancelled.",
        )


def test_chat_response_uses_primary_text_with_structured_sidecars() -> None:
    response = ChatResponse(
        session_id="session-1",
        primary_text="Which Marco do you mean?",
        pending_process=PendingProcessRef(
            process_id="process-1",
            kind=PendingProcessKind.MEMORY_INGESTION,
            question="Which Marco do you mean?",
        ),
    )

    dumped = response.model_dump(mode="json", exclude_none=True)

    assert dumped["primary_text"] == "Which Marco do you mean?"
    assert dumped["pending_process"]["process_id"] == "process-1"
    assert "parts" not in dumped


def test_in_memory_store_keeps_session_and_messages_separate() -> None:
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.WEB,
        external_conversation_id="web-conversation-1",
        owner_id="owner-1",
    )
    same_session = store.get_or_create_session(
        channel=ChatChannel.WEB,
        external_conversation_id="web-conversation-1",
        owner_id="owner-1",
    )
    store.append_message(
        ConversationMessage(
            session_id=session.session_id,
            role="user",
            text="Yesterday I met Marco.",
        ),
    )

    detail = store.get_session_detail(session.session_id)

    assert same_session.session_id == session.session_id
    assert detail.session.session_id == session.session_id
    assert detail.messages[0].text == "Yesterday I met Marco."


def test_runtime_routes_default_text_to_ingestion_facade() -> None:
    facade = RecordingFacade()
    runtime = ChatRuntime(store=InMemoryChatSessionStore(), tool_facade=facade)

    response = runtime.handle_message(_message(text="Yesterday I met Marco."))

    assert response.primary_text == "Memory accepted."
    assert facade.calls[0][0] == "start_memory_ingestion"
    request = facade.calls[0][1]
    assert isinstance(request, ChatToolRequest)
    assert request.text == "Yesterday I met Marco."


def test_runtime_attaches_pending_context_without_forcing_route() -> None:
    facade = RecordingFacade()
    runtime = ChatRuntime(store=InMemoryChatSessionStore(), tool_facade=facade)

    first_response = runtime.handle_message(_message(text="needs clarification", message_id="m1"))
    second_response = runtime.handle_message(
        _message(text="This is a different memory.", message_id="m2"),
    )

    assert first_response.status == ChatResponseStatus.NEEDS_USER_INPUT
    assert second_response.primary_text == "Memory accepted."
    assert facade.calls[1][0] == "start_memory_ingestion"
    request = facade.calls[1][1]
    assert isinstance(request, ChatToolRequest)
    assert request.pending_process_context is not None
    assert request.pending_process_context.process_ref.process_id == "process-1"


def test_runtime_commands_route_to_query_correction_and_cancel() -> None:
    facade = RecordingFacade()
    runtime = ChatRuntime(store=InMemoryChatSessionStore(), tool_facade=facade)

    runtime.handle_message(_message(text="/ask what happened in Greece?", message_id="m1"))
    runtime.handle_message(_message(text="/correct Marco was from university", message_id="m2"))
    runtime.handle_message(_message(text="/cancel", message_id="m3"))

    assert [call[0] for call in facade.calls] == [
        "query_memory_context",
        "propose_memory_correction",
        "cancel_pending_process",
    ]


def test_web_chat_api_requires_bearer_token_and_posts_message() -> None:
    facade = RecordingFacade()
    runtime = ChatRuntime(store=InMemoryChatSessionStore(), tool_facade=facade)
    client = _client(runtime)

    unauthorized = client.post("/chat/messages", json=_message_payload("hello"))
    authorized = client.post(
        "/chat/messages",
        json=_message_payload("hello"),
        headers={"Authorization": "Bearer test-token"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["primary_text"] == "Memory accepted."


def test_chat_api_get_session_and_cancel() -> None:
    facade = RecordingFacade()
    runtime = ChatRuntime(store=InMemoryChatSessionStore(), tool_facade=facade)
    client = _client(runtime)

    response = client.post(
        "/chat/messages",
        json=_message_payload("needs clarification"),
        headers={"Authorization": "Bearer test-token"},
    )
    session_id = response.json()["session_id"]

    session = client.get(
        f"/chat/sessions/{session_id}",
        headers={"Authorization": "Bearer test-token"},
    )
    cancelled = client.post(
        f"/chat/sessions/{session_id}/cancel",
        json={"owner_id": "owner-1"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert session.status_code == 200
    assert session.json()["pending_process"]["process_ref"]["process_id"] == "process-1"
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == ChatResponseStatus.CANCELLED.value


def _message(text: str, message_id: str = "message-1") -> IncomingChatMessage:
    return IncomingChatMessage(
        channel=ChatChannel.WEB,
        conversation_id="conversation-1",
        sender_id="sender-1",
        owner_id="owner-1",
        message_id=message_id,
        text=text,
    )


def _message_payload(text: str) -> dict[str, object]:
    return {
        "conversation_id": "conversation-1",
        "sender_id": "sender-1",
        "owner_id": "owner-1",
        "message_id": "message-1",
        "text": text,
    }


def _client(runtime: ChatRuntime) -> TestClient:
    app = FastAPI()
    app.include_router(chat_routes.router)
    app.dependency_overrides[chat_routes.get_chat_runtime] = lambda: runtime
    app.dependency_overrides[chat_routes.get_settings] = lambda: Settings(
        _env_file=None,
        WEB_CHAT_AUTH_TOKEN="test-token",
    )
    return TestClient(app)
