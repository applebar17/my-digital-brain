from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from my_digital_brain.api.routes import chat as chat_routes
from my_digital_brain.agentic import AgenticRuntime, AgenticStateRunner
from my_digital_brain.ai.schemas import ChatRequest, ChatResult, ProviderCallMetadata
from my_digital_brain.ai.tools import ToolBox
from my_digital_brain.chat.enums import (
    ChatChannel,
    ChatResponseStatus,
    PendingProcessKind,
    PendingProcessStatus,
)
from my_digital_brain.chat.clarification import build_clarification_packet
from my_digital_brain.chat.facade import (
    CancelPendingProcessRequest,
    ChatToolRequest,
    ChatToolResult,
)
from my_digital_brain.chat.models import (
    ChatResponse,
    ClarificationPacket,
    ConversationMessage,
    IncomingChatMessage,
    PendingProcessContext,
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
            packet = _clarification_packet(process_id="process-1")
            return ChatToolResult(
                status=ChatResponseStatus.NEEDS_USER_INPUT,
                primary_text="Which Marco do you mean?",
                pending_process=PendingProcessRef(
                    process_id="process-1",
                    kind=PendingProcessKind.MEMORY_INGESTION,
                    question="Which Marco do you mean?",
                    metadata={
                        "clarification_packet": packet.model_dump(
                            mode="json",
                            exclude_none=True,
                        )
                    },
                ),
                clarification_packet=packet,
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

    def update_memory_graph(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("update_memory_graph", request))
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="Graph update accepted.",
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

    def pause_pending_process(self, request: CancelPendingProcessRequest) -> ChatToolResult:
        self.calls.append(("pause_pending_process", request))
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="Paused.",
            metadata={"clear_pending_process": True},
        )

    def resume_pending_process(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("resume_pending_process", request))
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="Resumed.",
            metadata={"clear_pending_process": True},
        )


class ScriptedToolProvider:
    provider_name = "scripted"

    def __init__(self, steps: list[dict[str, object]]) -> None:
        self.steps = list(steps)
        self.calls: list[dict[str, object]] = []

    def generate_chat_with_tools(
        self,
        request: ChatRequest,
        *,
        toolbox: ToolBox,
        tools_mapping: dict[str, object],
        max_tool_calls: int | None = None,
    ) -> ChatResult:
        step = self.steps.pop(0) if self.steps else {"content": ""}
        self.calls.append({"request": request, "tool_names": sorted(toolbox.tools_by_name)})
        tool_name = step.get("tool")
        if isinstance(tool_name, str):
            tools_mapping[tool_name](**step.get("arguments", {}))
        return ChatResult(
            content=str(step.get("content") or ""),
            metadata=ProviderCallMetadata.fake(model=request.model),
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


def test_deterministic_runtime_does_not_route_default_text_to_ingestion() -> None:
    facade = RecordingFacade()
    runtime = ChatRuntime(store=InMemoryChatSessionStore(), tool_facade=facade)

    response = runtime.handle_message(_message(text="Yesterday I met Marco."))

    assert response.status == ChatResponseStatus.FAILED
    assert "AI conversation runtime is not enabled" in response.primary_text
    assert response.diagnostics[0].code == "ai_runtime_not_enabled"
    assert facade.calls == []


def test_deterministic_runtime_keeps_pending_context_but_does_not_force_route() -> None:
    facade = RecordingFacade()
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.WEB,
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    store.save_pending_process_context(
        session.session_id,
        PendingProcessContext(
            process_ref=PendingProcessRef(
                process_id="process-1",
                kind=PendingProcessKind.MEMORY_INGESTION,
                question="Which Marco do you mean?",
            ),
        ),
    )
    runtime = ChatRuntime(store=store, tool_facade=facade)

    response = runtime.handle_message(
        _message(text="This is a different memory.", message_id="m2"),
    )

    assert response.status == ChatResponseStatus.FAILED
    assert store.get_active_pending_process_context(session.session_id) is not None
    assert facade.calls == []


def test_store_can_pause_pending_process_and_list_paused_backlog() -> None:
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.WEB,
        external_conversation_id="web-conversation-1",
        owner_id="owner-1",
    )
    store.save_pending_process_context(
        session.session_id,
        PendingProcessContext(
            process_ref=PendingProcessRef(
                process_id="process-1",
                kind=PendingProcessKind.MEMORY_INGESTION,
                question="Which Marco?",
            ),
            context={
                "summary": "Trying to store a memory about Marco.",
                "source_text": "Yesterday I met Marco.",
                "unresolved_targets": ["person: Marco"],
            },
        ),
    )

    paused = store.update_pending_process_status(
        session.session_id,
        "process-1",
        PendingProcessStatus.PAUSED,
        metadata={"pause_reason": "not now"},
        context_updates={"resumable": True},
    )

    assert paused.process_ref.status == PendingProcessStatus.PAUSED
    assert paused.context["source_text"] == "Yesterday I met Marco."
    assert paused.context["resumable"] is True
    assert store.get_active_pending_process_context(session.session_id) is None
    backlog = store.list_pending_process_contexts(
        session.session_id,
        statuses={PendingProcessStatus.PAUSED},
    )
    assert [item.process_ref.process_id for item in backlog] == ["process-1"]


def test_agentic_context_contains_compact_pending_overview_without_backend_snapshot() -> None:
    provider = ScriptedToolProvider([{"content": "I can continue that later."}])
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.WEB,
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    store.save_pending_process_context(
        session.session_id,
        PendingProcessContext(
            process_ref=PendingProcessRef(
                process_id="process-1",
                kind=PendingProcessKind.MEMORY_INGESTION,
                question="Which Marco?",
            ),
            context={
                "summary": "Trying to store a memory about Marco in Milan.",
                "source_text": "Yesterday I met Marco in Milan.",
                "candidate_graph_snapshot": {"raw": "hidden"},
                "unresolved_targets": ["person: Marco"],
            },
        ),
    )
    store.update_pending_process_status(
        session.session_id,
        "process-1",
        PendingProcessStatus.PAUSED,
        context_updates={"resumable": True},
    )
    runtime = ChatRuntime(
        store=store,
        tool_facade=RecordingFacade(),
        runtime_mode="agentic",
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )

    response = runtime.handle_message(_message(text="Marco from university"))
    system_prompt = provider.calls[0]["request"].messages[0].content
    latest_user_message = provider.calls[0]["request"].messages[1].content

    assert response.metadata["visited_states"] == ["conversation_entry"]
    assert latest_user_message == "Marco from university"
    assert "pending_processes" in system_prompt
    assert "Trying to store a memory about Marco in Milan." in system_prompt
    assert "candidate_graph_snapshot" not in system_prompt
    assert "Yesterday I met Marco in Milan." not in system_prompt


def test_runtime_commands_route_to_query_correction_and_cancel() -> None:
    facade = RecordingFacade()
    runtime = ChatRuntime(
        store=InMemoryChatSessionStore(),
        tool_facade=facade,
        debug_commands_enabled=True,
    )

    runtime.handle_message(_message(text="/ask what happened in Greece?", message_id="m1"))
    runtime.handle_message(_message(text="/correct Marco was from university", message_id="m2"))
    runtime.handle_message(_message(text="/cancel", message_id="m3"))

    assert [call[0] for call in facade.calls] == [
        "query_memory_context",
        "update_memory_graph",
        "cancel_pending_process",
    ]


def test_runtime_debug_commands_are_disabled_by_default() -> None:
    facade = RecordingFacade()
    runtime = ChatRuntime(store=InMemoryChatSessionStore(), tool_facade=facade)

    response = runtime.handle_message(_message(text="/status", message_id="m1"))

    assert response.status == ChatResponseStatus.FAILED
    assert response.diagnostics[0].code == "ai_runtime_not_enabled"
    assert facade.calls == []


def test_agentic_runtime_mode_returns_direct_assistant_response_and_persists_it() -> None:
    provider = ScriptedToolProvider([{"content": "I can help with that."}])
    store = InMemoryChatSessionStore()
    runtime = ChatRuntime(
        store=store,
        tool_facade=RecordingFacade(),
        runtime_mode="agentic",
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )

    response = runtime.handle_message(_message(text="hello"))
    detail = store.get_session_detail(response.session_id)

    assert response.primary_text == "I can help with that."
    assert response.metadata["runtime_mode"] == "agentic"
    assert response.metadata["visited_states"] == ["conversation_entry"]
    assert detail.messages[-1].role == "assistant"
    assert detail.messages[-1].text == "I can help with that."


def test_agentic_runtime_mode_keeps_pending_context_in_conversation_entry() -> None:
    provider = ScriptedToolProvider([{"content": "Which Marco did you mean?"}])
    store = InMemoryChatSessionStore()
    facade = RecordingFacade()
    session = store.get_or_create_session(
        channel=ChatChannel.WEB,
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    store.save_pending_process_context(
        session.session_id,
        PendingProcessContext(
            process_ref=PendingProcessRef(
                process_id="process-1",
                kind=PendingProcessKind.MEMORY_INGESTION,
                question="Which Marco do you mean?",
            ),
        ),
    )
    runtime = ChatRuntime(
        store=store,
        tool_facade=facade,
        runtime_mode="agentic",
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )

    response = runtime.handle_message(_message(text="I'm not sure", message_id="m2"))

    assert response.metadata["visited_states"] == ["conversation_entry"]
    assert provider.calls[0]["tool_names"] == [
        "query_memory_context",
        "start_memory_ingestion",
        "update_memory_graph",
    ]


def test_agentic_ingestion_clarification_is_rendered_and_stored_as_pending() -> None:
    provider = ScriptedToolProvider(
        [
            {
                "content": "Routing to ingestion.",
                "tool": "start_memory_ingestion",
                "arguments": {"source_text": "needs clarification"},
            }
        ]
    )
    store = InMemoryChatSessionStore()
    runtime = ChatRuntime(
        store=store,
        tool_facade=RecordingFacade(),
        runtime_mode="agentic",
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )

    response = runtime.handle_message(_message(text="needs clarification"))
    detail = store.get_session_detail(response.session_id)

    assert response.status == ChatResponseStatus.NEEDS_USER_INPUT
    assert response.primary_text == "Which Marco do you mean?"
    assert response.pending_process is not None
    assert response.clarification_packet is not None
    assert response.clarification_packet.history_delta[0].role == "assistant"
    assert "Which Marco do you mean?" in response.clarification_packet.history_delta[0].content
    assert detail.pending_process.process_ref.process_id == response.pending_process.process_id
    assert detail.messages[-1].role == "assistant"
    assert detail.messages[-1].pending_process_id == response.pending_process.process_id
    assert "Clarification needed:" in (detail.messages[-1].text or "")
    assert "history_delta" in detail.messages[-1].metadata
    assert "compact_trace" not in response.metadata


def test_clarification_answer_endpoint_validates_and_resumes_pending_process() -> None:
    provider = ScriptedToolProvider([])
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.WEB,
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    packet = _clarification_packet(process_id="process-1")
    store.save_pending_process_context(
        session.session_id,
        PendingProcessContext(
            process_ref=PendingProcessRef(
                process_id="process-1",
                kind=PendingProcessKind.MEMORY_INGESTION,
                question=packet.questions[0].question,
                metadata={"clarification_packet": packet.model_dump(mode="json")},
            ),
            context={
                "summary": "Need Marco disambiguation.",
                "source_text": "Yesterday I met Marco in Milan.",
                "clarification_packet": packet.model_dump(mode="json"),
            },
        ),
    )
    runtime = ChatRuntime(
        store=store,
        tool_facade=RecordingFacade(),
        runtime_mode="agentic",
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )
    client = _client(runtime)
    option_id = packet.questions[0].options[0].option_id

    response = client.post(
        f"/chat/sessions/{session.session_id}/clarifications/process-1/answers",
        json={
            "owner_id": "owner-1",
            "sender_id": "sender-1",
            "message_id": "clarification-message-1",
            "answer_packet": {
                "packet_id": packet.packet_id,
                "process_id": packet.process_id,
                "answers": [
                    {
                        "question_id": packet.questions[0].question_id,
                        "selected_option_ids": [option_id],
                        "free_text": None,
                    }
                ],
            },
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["primary_text"] == "Resumed."
    assert provider.calls == []
    messages = runtime.get_session_detail(session.session_id).messages
    assert messages[-2].role == "user"
    assert "Clarification answers:" in messages[-2].text
    assert store.get_pending_process_context("process-1").process_ref.status == (
        PendingProcessStatus.COMPLETED
    )


def test_clarification_answer_endpoint_resumes_graph_update_state_directly() -> None:
    provider = ScriptedToolProvider([{"content": "Graph update resumed."}])
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.WEB,
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    packet = _clarification_packet(process_id="process-1")
    store.save_pending_process_context(
        session.session_id,
        PendingProcessContext(
            process_ref=PendingProcessRef(
                process_id="process-1",
                kind=PendingProcessKind.MEMORY_UPDATE,
                question=packet.questions[0].question,
                metadata={
                    "clarification_packet": packet.model_dump(mode="json"),
                    "guidelines": "Apply as correction.",
                    "desired_work": "correct_or_update_memory_graph",
                },
            ),
            context={
                "source_text": "Marco was from work.",
                "target_ids": ["node-marco"],
                "clarification_packet": packet.model_dump(mode="json"),
            },
        ),
    )
    runtime = ChatRuntime(
        store=store,
        tool_facade=RecordingFacade(),
        runtime_mode="agentic",
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )
    client = _client(runtime)
    option_id = packet.questions[0].options[0].option_id

    response = client.post(
        f"/chat/sessions/{session.session_id}/clarifications/process-1/answers",
        json={
            "owner_id": "owner-1",
            "sender_id": "sender-1",
            "message_id": "clarification-message-1",
            "answer_packet": {
                "packet_id": packet.packet_id,
                "process_id": packet.process_id,
                "answers": [
                    {
                        "question_id": packet.questions[0].question_id,
                        "selected_option_ids": [option_id],
                        "free_text": "Marco from university.",
                    }
                ],
            },
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["primary_text"] == "Graph update resumed."
    assert response.json()["metadata"]["resumed_operation"] == "graph_update"
    assert provider.calls[0]["tool_names"] == [
        "create_graph_node",
        "create_memory_log",
        "create_relationship_state",
        "get_context_package",
        "get_entity_detail",
        "get_neighborhood_view",
        "get_target_evidence",
        "get_timeline",
        "patch_graph_node",
        "request_user_clarification",
        "resolve_graph_update_targets",
        "upsert_graph_relationship",
    ]
    assert store.get_pending_process_context("process-1").process_ref.status == (
        PendingProcessStatus.COMPLETED
    )


def test_clarification_answer_endpoint_rejects_unknown_option_id() -> None:
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.WEB,
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    packet = _clarification_packet(process_id="process-1")
    store.save_pending_process_context(
        session.session_id,
        PendingProcessContext(
            process_ref=PendingProcessRef(
                process_id="process-1",
                kind=PendingProcessKind.MEMORY_INGESTION,
                question=packet.questions[0].question,
                metadata={"clarification_packet": packet.model_dump(mode="json")},
            ),
            context={"clarification_packet": packet.model_dump(mode="json")},
        ),
    )
    runtime = ChatRuntime(
        store=store,
        tool_facade=RecordingFacade(),
        runtime_mode="agentic",
        agentic_runtime=AgenticRuntime(AgenticStateRunner(ScriptedToolProvider([]))),
    )
    client = _client(runtime)

    response = client.post(
        f"/chat/sessions/{session.session_id}/clarifications/process-1/answers",
        json={
            "owner_id": "owner-1",
            "message_id": "clarification-message-1",
            "answer_packet": {
                "packet_id": packet.packet_id,
                "process_id": packet.process_id,
                "answers": [
                    {
                        "question_id": packet.questions[0].question_id,
                        "selected_option_ids": ["invented-option"],
                        "free_text": None,
                    }
                ],
            },
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 400
    assert "unknown option ids" in response.json()["detail"]


def test_web_chat_api_requires_bearer_token_and_posts_message() -> None:
    facade = RecordingFacade()
    provider = ScriptedToolProvider([{"content": "I can help with that."}])
    runtime = ChatRuntime(
        store=InMemoryChatSessionStore(),
        tool_facade=facade,
        runtime_mode="agentic",
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )
    client = _client(runtime)

    unauthorized = client.post("/chat/messages", json=_message_payload("hello"))
    authorized = client.post(
        "/chat/messages",
        json=_message_payload("hello"),
        headers={"Authorization": "Bearer test-token"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["primary_text"] == "I can help with that."


def test_chat_api_get_session_and_cancel() -> None:
    facade = RecordingFacade()
    provider = ScriptedToolProvider(
        [
            {
                "content": "Routing to ingestion.",
                "tool": "start_memory_ingestion",
                "arguments": {"source_text": "needs clarification"},
            },
        ]
    )
    runtime = ChatRuntime(
        store=InMemoryChatSessionStore(),
        tool_facade=facade,
        runtime_mode="agentic",
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )
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


def test_chat_api_create_list_update_and_post_to_selected_session() -> None:
    provider = ScriptedToolProvider([{"content": "Stored in selected chat."}])
    runtime = ChatRuntime(
        store=InMemoryChatSessionStore(),
        tool_facade=RecordingFacade(),
        runtime_mode="agentic",
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )
    client = _client(runtime)
    headers = {"Authorization": "Bearer test-token"}

    created = client.post(
        "/chat/sessions",
        json={"owner_id": "owner-1", "channel": "web", "title": "New chat"},
        headers=headers,
    )
    session_id = created.json()["session_id"]
    posted = client.post(
        "/chat/messages",
        json=_message_payload("hello in selected chat", session_id=session_id),
        headers=headers,
    )
    listed = client.get(
        "/chat/sessions",
        params={"owner_id": "owner-1", "channel": "web"},
        headers=headers,
    )
    renamed = client.patch(
        f"/chat/sessions/{session_id}",
        json={"title": "Renamed from API"},
        headers=headers,
    )
    archived = client.patch(
        f"/chat/sessions/{session_id}",
        json={"status": "archived"},
        headers=headers,
    )
    listed_after_archive = client.get(
        "/chat/sessions",
        params={"owner_id": "owner-1", "channel": "web"},
        headers=headers,
    )

    assert created.status_code == 200
    assert posted.status_code == 200
    assert posted.json()["session_id"] == session_id
    assert listed.status_code == 200
    assert listed.json()["sessions"][0]["session_id"] == session_id
    assert listed.json()["sessions"][0]["last_message_preview"] == "Stored in selected chat."
    assert renamed.json()["title"] == "Renamed from API"
    assert archived.json()["status"] == "archived"
    assert listed_after_archive.json()["sessions"] == []


def _message(text: str, message_id: str = "message-1") -> IncomingChatMessage:
    return IncomingChatMessage(
        channel=ChatChannel.WEB,
        conversation_id="conversation-1",
        sender_id="sender-1",
        owner_id="owner-1",
        message_id=message_id,
        text=text,
    )


def _message_payload(text: str, session_id: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "conversation_id": "conversation-1",
        "sender_id": "sender-1",
        "owner_id": "owner-1",
        "message_id": "message-1",
        "text": text,
    }
    if session_id is not None:
        payload["session_id"] = session_id
    return payload


def _clarification_packet(process_id: str) -> ClarificationPacket:
    return build_clarification_packet(
        process_id=process_id,
        origin_state_id="memory_ingestion",
        reason="Multiple Marco candidates exist.",
        compact_summary="Need to know which Marco the user means.",
        target_refs=["NODE_000001", "NODE_000002"],
        questions=[
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


def _client(runtime: ChatRuntime) -> TestClient:
    app = FastAPI()
    app.include_router(chat_routes.router)
    app.dependency_overrides[chat_routes.get_chat_runtime] = lambda: runtime
    app.dependency_overrides[chat_routes.get_settings] = lambda: Settings(
        _env_file=None,
        LLM_PROVIDER="openai",
        WEB_CHAT_AUTH_TOKEN="test-token",
    )
    return TestClient(app)
