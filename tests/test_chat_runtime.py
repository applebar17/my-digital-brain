from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from my_digital_brain.api.routes import chat as chat_routes
from my_digital_brain.agentic import AgenticRuntime, AgenticStateRunner
from my_digital_brain.ai.client.tool_execution import ToolCallInterruption
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
    AgenticFrame,
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
            packet = _clarification_packet(frame_id="facade-frame")
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
            tool_call_id = f"call-{len(self.calls)}"
            assistant_message = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": _json_arguments(step.get("arguments", {})),
                        },
                    }
                ],
            }
            tool_fn = tools_mapping[tool_name]
            context = getattr(tool_fn, "_agentic_execution_context", None)
            previous_tool_call_id = getattr(context, "current_tool_call_id", None)
            previous_tool_name = getattr(context, "current_tool_name", None)
            if context is not None:
                context.current_tool_call_id = tool_call_id
                context.current_tool_name = tool_name
            try:
                tool_result = tool_fn(**step.get("arguments", {}))
            finally:
                if context is not None:
                    context.current_tool_call_id = previous_tool_call_id
                    context.current_tool_name = previous_tool_name
            if getattr(tool_result, "status", None) == "interrupted":
                raise ToolCallInterruption(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    result=tool_result,
                    messages=[
                        *[
                            message.model_dump(mode="json", exclude_none=True)
                            for message in request.messages
                        ],
                        assistant_message,
                    ],
                )
        return ChatResult(
            content=str(step.get("content") or ""),
            metadata=ProviderCallMetadata.fake(model=request.model),
        )


def _json_arguments(arguments: object) -> str:
    return json.dumps(arguments if isinstance(arguments, dict) else {}, sort_keys=True)


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


def test_chat_runtime_requires_agentic_runtime() -> None:
    facade = RecordingFacade()

    try:
        ChatRuntime(store=InMemoryChatSessionStore(), tool_facade=facade)
    except Exception as exc:
        assert "requires an AgenticRuntime" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("ChatRuntime should fail without an AgenticRuntime")

    assert facade.calls == []

def test_agentic_runtime_ignores_legacy_pending_context() -> None:
    provider = ScriptedToolProvider([{"content": "Handled as a normal message."}])
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
    runtime = ChatRuntime(
        store=store,
        tool_facade=facade,
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )

    response = runtime.handle_message(
        _message(text="This is a different memory.", message_id="m2"),
    )
    system_prompt = provider.calls[0]["request"].messages[0].content

    assert response.status == ChatResponseStatus.OK
    assert "pending_process" not in system_prompt
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


def test_agentic_context_does_not_include_pending_process_overview() -> None:
    provider = ScriptedToolProvider([{"content": "I can continue normally."}])
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
                "candidate_graph_snapshot": {"raw": "hidden"},
            },
        ),
    )
    runtime = ChatRuntime(
        store=store,
        tool_facade=RecordingFacade(),
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )

    response = runtime.handle_message(_message(text="Marco from university"))
    system_prompt = provider.calls[0]["request"].messages[0].content

    assert response.metadata["visited_states"] == ["conversation_entry"]
    assert "pending_processes" not in system_prompt
    assert "Trying to store a memory" not in system_prompt
    assert "candidate_graph_snapshot" not in system_prompt

def test_debug_commands_are_normal_agentic_messages() -> None:
    facade = RecordingFacade()
    provider = ScriptedToolProvider([
        {"content": "Ask handled normally."},
        {"content": "Correction handled normally."},
        {"content": "Cancel handled normally."},
    ])
    runtime = ChatRuntime(
        store=InMemoryChatSessionStore(),
        tool_facade=facade,
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
        debug_commands_enabled=True,
    )

    first = runtime.handle_message(_message(text="/ask what happened in Greece?", message_id="m1"))
    second = runtime.handle_message(_message(text="/correct Marco was from university", message_id="m2"))
    third = runtime.handle_message(_message(text="/cancel", message_id="m3"))

    assert [first.primary_text, second.primary_text, third.primary_text] == [
        "Ask handled normally.",
        "Correction handled normally.",
        "Cancel handled normally.",
    ]
    assert facade.calls == []

def test_debug_commands_do_not_enable_facade_fallback_by_default() -> None:
    facade = RecordingFacade()
    provider = ScriptedToolProvider([{"content": "Status handled normally."}])
    runtime = ChatRuntime(
        store=InMemoryChatSessionStore(),
        tool_facade=facade,
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )

    response = runtime.handle_message(_message(text="/status", message_id="m1"))

    assert response.status == ChatResponseStatus.OK
    assert response.primary_text == "Status handled normally."
    assert facade.calls == []

def test_agentic_runtime_mode_returns_direct_assistant_response_and_persists_it() -> None:
    provider = ScriptedToolProvider([{"content": "I can help with that."}])
    store = InMemoryChatSessionStore()
    runtime = ChatRuntime(
        store=store,
        tool_facade=RecordingFacade(),
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )

    response = runtime.handle_message(_message(text="hello"))
    detail = store.get_session_detail(response.session_id)

    assert response.primary_text == "I can help with that."
    assert response.metadata["runtime_mode"] == "agentic"
    assert response.metadata["visited_states"] == ["conversation_entry"]
    assert detail.messages[-1].role == "assistant"
    assert detail.messages[-1].text == "I can help with that."


def test_agentic_runtime_does_not_inject_pending_context_into_conversation_entry() -> None:
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
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )

    response = runtime.handle_message(_message(text="I'm not sure", message_id="m2"))
    system_prompt = provider.calls[0]["request"].messages[0].content

    assert response.metadata["visited_states"] == ["conversation_entry"]
    assert provider.calls[0]["tool_names"] == ["ingest_memory", "query_memory"]
    assert "pending_process" not in system_prompt

def test_agentic_ingestion_runs_without_pending_process() -> None:
    provider = ScriptedToolProvider(
        [
            {"content": "Routing to ingestion.", "tool": "ingest_memory", "arguments": {}},
            {"content": "Memory ingestion complete."},
        ]
    )
    store = InMemoryChatSessionStore()
    runtime = ChatRuntime(
        store=store,
        tool_facade=RecordingFacade(),
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )

    response = runtime.handle_message(_message(text="Remember this memory."))
    detail = store.get_session_detail(response.session_id)

    assert response.status == ChatResponseStatus.OK
    assert response.pending_process is None
    assert response.clarification_packet is None
    assert detail.active_agentic_frame is None
    assert detail.pending_process is None
    assert detail.messages[-1].pending_process_id is None
    assert response.metadata["agentic_status"] == "ok"
    assert provider.calls[0]["tool_names"] == ["ingest_memory", "query_memory"]
    assert provider.calls[1]["tool_names"] == [
        "get_context_package",
        "get_entity_detail",
        "get_neighborhood_view",
        "get_target_evidence",
        "request_user_clarification",
        "run_memory_creation",
        "update_memory_graph",
    ]

def test_clarification_answer_endpoint_validates_and_resumes_agentic_frame() -> None:
    provider = ScriptedToolProvider([{"content": "Resumed."}])
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.WEB,
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    packet = _save_interrupted_frame(store, session.session_id, state_id="memory_query")
    runtime = ChatRuntime(
        store=store,
        tool_facade=RecordingFacade(),
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )
    client = _client(runtime)
    option_id = packet.questions[0].options[0].option_id

    response = client.post(
        f"/chat/sessions/{session.session_id}/clarifications/{packet.frame_id}/answers",
        json={
            "owner_id": "owner-1",
            "sender_id": "sender-1",
            "message_id": "clarification-message-1",
            "answer_packet": {
                "packet_id": packet.packet_id,
                "frame_id": packet.frame_id,
                "tool_call_id": packet.tool_call_id,
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
    assert provider.calls[0]["request"].messages[-1].role == "tool"
    assert provider.calls[0]["request"].messages[-1].tool_call_id == packet.tool_call_id
    messages = runtime.get_session_detail(session.session_id).messages
    assert messages[-2].role == "user"
    assert "Clarification answers:" in messages[-2].text
    assert messages[-2].metadata["ui_hidden"] is True
    assert messages[-2].metadata["message_kind"] == "clarification_answer"
    assert store.get_agentic_frame(packet.frame_id).status == "completed"


def test_clarification_answer_endpoint_accumulates_multi_question_progress_before_resuming() -> None:
    provider = ScriptedToolProvider([{"content": "Resumed after all answers."}])
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.WEB,
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    packet = _save_interrupted_frame(
        store,
        session.session_id,
        state_id="memory_query",
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
            },
            {
                "question_id": "question-2",
                "question": "What context should I keep?",
                "options": [],
                "free_text_allowed": True,
            },
        ],
    )
    runtime = ChatRuntime(
        store=store,
        tool_facade=RecordingFacade(),
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )
    client = _client(runtime)

    first_response = client.post(
        f"/chat/sessions/{session.session_id}/clarifications/{packet.frame_id}/answers",
        json={
            "owner_id": "owner-1",
            "sender_id": "sender-1",
            "message_id": "clarification-message-1",
            "answer_packet": {
                "packet_id": packet.packet_id,
                "frame_id": packet.frame_id,
                "tool_call_id": packet.tool_call_id,
                "answers": [
                    {
                        "question_id": "question-1",
                        "selected_option_ids": ["option-marco-university"],
                        "free_text": None,
                    }
                ],
            },
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["status"] == ChatResponseStatus.AWAITING_CLARIFICATION.value
    assert first_payload["clarification_packet"]["packet_id"] == packet.packet_id
    progress = first_payload["metadata"]["clarification_progress"]
    assert progress["answered_question_ids"] == ["question-1"]
    assert progress["current_question_id"] == "question-2"
    assert progress["is_complete"] is False
    assert provider.calls == []
    frame = store.get_agentic_frame(packet.frame_id)
    assert frame.status == "interrupted"
    assert frame.metadata["clarification_progress"]["answers_by_question_id"][
        "question-1"
    ]["selected_option_ids"] == ["option-marco-university"]
    messages = runtime.get_session_detail(session.session_id).messages
    assert messages[-2].metadata["message_kind"] == "clarification_answer"
    assert messages[-2].metadata["ui_hidden"] is True
    assert messages[-1].metadata["message_kind"] == "clarification_prompt"
    assert messages[-1].metadata["ui_hidden"] is True

    final_response = client.post(
        f"/chat/sessions/{session.session_id}/clarifications/{packet.frame_id}/answers",
        json={
            "owner_id": "owner-1",
            "sender_id": "sender-1",
            "message_id": "clarification-message-2",
            "answer_packet": {
                "packet_id": packet.packet_id,
                "frame_id": packet.frame_id,
                "tool_call_id": packet.tool_call_id,
                "answers": [
                    {
                        "question_id": "question-2",
                        "selected_option_ids": [],
                        "free_text": "Keep that we met in Milan.",
                    }
                ],
            },
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert final_response.status_code == 200
    assert final_response.json()["primary_text"] == "Resumed after all answers."
    assert len(provider.calls) == 1
    tool_message = provider.calls[0]["request"].messages[-1]
    assert tool_message.role == "tool"
    assert tool_message.tool_call_id == packet.tool_call_id
    assert "Marco from university" in tool_message.content
    assert "Keep that we met in Milan." in tool_message.content
    assert store.get_agentic_frame(packet.frame_id).status == "completed"


def test_clarification_answer_endpoint_resumes_graph_update_state_directly() -> None:
    provider = ScriptedToolProvider([{"content": "Graph update resumed."}])
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.WEB,
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    packet = _save_interrupted_frame(
        store,
        session.session_id,
        frame_id="graph-frame-1",
        tool_call_id="graph-call-1",
        state_id="graph_update",
    )
    runtime = ChatRuntime(
        store=store,
        tool_facade=RecordingFacade(),
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )
    client = _client(runtime)
    option_id = packet.questions[0].options[0].option_id

    response = client.post(
        f"/chat/sessions/{session.session_id}/clarifications/{packet.frame_id}/answers",
        json={
            "owner_id": "owner-1",
            "sender_id": "sender-1",
            "message_id": "clarification-message-1",
            "answer_packet": {
                "packet_id": packet.packet_id,
                "frame_id": packet.frame_id,
                "tool_call_id": packet.tool_call_id,
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
    assert response.json()["metadata"]["resumed_frame_id"] == packet.frame_id
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
    assert store.get_agentic_frame(packet.frame_id).status == "completed"


def test_clarification_answer_endpoint_rejects_unknown_option_id() -> None:
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel=ChatChannel.WEB,
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    packet = _save_interrupted_frame(store, session.session_id, state_id="memory_query")
    runtime = ChatRuntime(
        store=store,
        tool_facade=RecordingFacade(),
        agentic_runtime=AgenticRuntime(AgenticStateRunner(ScriptedToolProvider([]))),
    )
    client = _client(runtime)

    response = client.post(
        f"/chat/sessions/{session.session_id}/clarifications/{packet.frame_id}/answers",
        json={
            "owner_id": "owner-1",
            "message_id": "clarification-message-1",
            "answer_packet": {
                "packet_id": packet.packet_id,
                "frame_id": packet.frame_id,
                "tool_call_id": packet.tool_call_id,
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


def test_chat_api_get_session_and_cancel_removed_pending_process_path() -> None:
    provider = ScriptedToolProvider([{"content": "Normal response."}])
    runtime = ChatRuntime(
        store=InMemoryChatSessionStore(),
        tool_facade=RecordingFacade(),
        agentic_runtime=AgenticRuntime(AgenticStateRunner(provider=provider)),
    )
    client = _client(runtime)

    response = client.post(
        "/chat/messages",
        json=_message_payload("hello"),
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
    assert session.json()["pending_process"] is None
    assert session.json()["active_agentic_frame"] is None
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == ChatResponseStatus.FAILED.value
    assert cancelled.json()["diagnostics"][0]["code"] == "pending_process_cancel_removed"

def test_chat_api_create_list_update_and_post_to_selected_session() -> None:
    provider = ScriptedToolProvider([{"content": "Stored in selected chat."}])
    runtime = ChatRuntime(
        store=InMemoryChatSessionStore(),
        tool_facade=RecordingFacade(),
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


def _save_interrupted_frame(
    store: InMemoryChatSessionStore,
    session_id: str,
    *,
    frame_id: str = "frame-1",
    tool_call_id: str = "call-1",
    state_id: str = "memory_query",
    questions: list[dict[str, object]] | None = None,
) -> ClarificationPacket:
    packet = _clarification_packet(
        frame_id=frame_id,
        tool_call_id=tool_call_id,
        state_id=state_id,
        questions=questions,
    )
    store.save_agentic_frame(
        session_id,
        AgenticFrame(
            frame_id=frame_id,
            session_id=session_id,
            state_id=state_id,
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
                                "name": "request_user_clarification",
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
            active_tool_name="request_user_clarification",
            clarification_packet=packet,
        ),
    )
    return packet


def _clarification_packet(
    frame_id: str,
    *,
    tool_call_id: str | None = "call-1",
    state_id: str = "memory_ingestion",
    questions: list[dict[str, object]] | None = None,
) -> ClarificationPacket:
    return build_clarification_packet(
        frame_id=frame_id,
        tool_call_id=tool_call_id,
        tool_name="request_user_clarification" if tool_call_id else None,
        origin_state_id=state_id,
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
