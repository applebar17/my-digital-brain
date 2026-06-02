from __future__ import annotations

from typing import Any

from my_digital_brain.agentic import (
    AgenticRuntime,
    AgenticStateId,
    AgenticStateInvocation,
    AgenticStateRunner,
    AgenticToolExecutionContext,
    ChannelSessionMetadata,
    ConversationContext,
    CorrectionIntakeContext,
    NeutralConversationMessage,
    PendingProcessContext,
    QueryRetrievalPlanningContext,
)
from my_digital_brain.ai.schemas import ChatRequest, ChatResult, ProviderCallMetadata
from my_digital_brain.ai.tools import ToolBox
from my_digital_brain.chat.enums import ChatResponseStatus
from my_digital_brain.chat.facade import ChatToolRequest, ChatToolResult


class ScriptedToolCallingProvider:
    provider_name = "scripted"

    def __init__(self, steps: list[dict[str, Any]]) -> None:
        self.steps = list(steps)
        self.calls: list[dict[str, Any]] = []

    def generate_chat_with_tools(
        self,
        request: ChatRequest,
        *,
        toolbox: ToolBox,
        tools_mapping: dict[str, Any],
        max_tool_calls: int | None = None,
    ) -> ChatResult:
        step = self.steps.pop(0) if self.steps else {"content": ""}
        self.calls.append(
            {
                "request": request,
                "toolbox": toolbox,
                "tool_names": sorted(toolbox.tools_by_name),
                "max_tool_calls": max_tool_calls,
            }
        )
        tool_name = step.get("tool")
        if tool_name:
            assert tool_name in toolbox.tools_by_name
            tools_mapping[tool_name](**step.get("arguments", {}))
        return ChatResult(
            content=step.get("content", ""),
            metadata=ProviderCallMetadata.fake(model=request.model),
        )

    def generate_chat(self, request: ChatRequest) -> ChatResult:
        return ChatResult(
            content="plain chat",
            metadata=ProviderCallMetadata.fake(model=request.model),
        )


class FakeGraphService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def get_context_package(
        self,
        node_id: str,
        *,
        include_history: bool = True,
        timeline_limit: int = 20,
        relationship_limit: int = 50,
    ) -> dict[str, Any]:
        self.calls.append(("get_context_package", node_id))
        return {
            "target": {"alias": "NODE_000001", "title": "Marco"},
            "current_facts": [{"description": "University friend"}],
            "alias_map": {"NODE_000001": node_id},
        }


class FakeBackendFacade:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ChatToolRequest]] = []

    def start_memory_ingestion(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("start_memory_ingestion", request))
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="Memory accepted by backend.",
            metadata={"operation": "start_memory_ingestion"},
        )


def _conversation(text: str = "What do I remember about Marco?") -> ConversationContext:
    return ConversationContext(
        current_message=NeutralConversationMessage.user(text),
        history=[
            NeutralConversationMessage.user("I met Marco yesterday."),
            NeutralConversationMessage.assistant("I received this memory."),
        ],
        timezone="Europe/Rome",
        channel_metadata=ChannelSessionMetadata(
            channel="telegram",
            conversation_id="chat-1",
            owner_id="owner-1",
            session_id="session-1",
            sender_id="sender-1",
        ),
    )


def _runner(provider: ScriptedToolCallingProvider) -> AgenticStateRunner:
    return AgenticStateRunner(provider=provider)


def test_conversation_entry_without_tool_call_returns_terminal_assistant_response() -> None:
    provider = ScriptedToolCallingProvider(
        [{"content": "I can help you store or query memories."}]
    )
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(_conversation("hello"), AgenticToolExecutionContext())

    assert result.status == "ok"
    assert result.final_text == "I can help you store or query memories."
    assert result.visited_states == [AgenticStateId.CONVERSATION_ENTRY.value]
    assert result.state_results[0].terminal is True
    prompt_payload = provider.calls[0]["request"].messages[1].content
    assert "channel_metadata" not in str(prompt_payload)


def test_conversation_entry_query_tool_hands_off_to_memory_query_state() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Routing to memory query.",
                "tool": "query_memory_context",
                "arguments": {
                    "question": "What do I remember about Marco?",
                    "seed_id": "node-marco",
                },
            },
            {
                "content": "Marco is stored as your university friend.",
                "tool": "get_context_package",
                "arguments": {"node_id": "node-marco"},
            },
        ]
    )
    graph = FakeGraphService()
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(
        _conversation(),
        AgenticToolExecutionContext(graph_service=graph),
    )

    assert result.status == "ok"
    assert result.final_text == "Marco is stored as your university friend."
    assert result.visited_states == [
        AgenticStateId.CONVERSATION_ENTRY.value,
        AgenticStateId.MEMORY_QUERY.value,
    ]
    assert result.state_results[0].handoff_target == "memory_query"
    assert result.state_results[1].tool_events[0].tool_name == "get_context_package"
    assert graph.calls == [("get_context_package", "node-marco")]
    assert provider.calls[0]["max_tool_calls"] == 3


def test_correction_handoff_reaches_confirmation_aware_specialist_state() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Routing to correction intake.",
                "tool": "propose_memory_correction",
                "arguments": {
                    "correction_text": "Marco was from university, not work.",
                    "target_id": "node-marco",
                },
            },
            {
                "content": "Should I update Marco?",
                "tool": "request_user_confirmation",
                "arguments": {
                    "question": "Should I update Marco?",
                    "proposal": {"target_id": "node-marco", "field_path": "description"},
                    "target_refs": ["node-marco"],
                },
            },
        ]
    )
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(
        _conversation("Marco was from university, not work."),
        AgenticToolExecutionContext(),
    )

    assert result.status == "ok"
    assert result.visited_states == [
        AgenticStateId.CONVERSATION_ENTRY.value,
        AgenticStateId.CORRECTION_INTAKE.value,
    ]
    confirmation = result.state_results[1].tool_events[0].data["confirmation"]
    assert confirmation["required_user_action"] == "confirm_or_cancel"
    assert confirmation["proposal"]["target_id"] == "node-marco"


def test_pending_context_starts_from_pending_process_review() -> None:
    provider = ScriptedToolCallingProvider(
        [{"content": "Which Marco did you mean?"}]
    )
    runtime = AgenticRuntime(_runner(provider))
    conversation = _conversation("I am not sure")
    conversation.pending_process = PendingProcessContext(
        process_id="process-1",
        kind="memory_ingestion",
        status="pending",
        question="Which Marco?",
    )

    result = runtime.run(conversation, AgenticToolExecutionContext())

    assert result.visited_states == [AgenticStateId.PENDING_PROCESS_REVIEW.value]
    assert provider.calls[0]["tool_names"] == [
        "cancel_pending_process",
        "pause_pending_process",
        "propose_memory_correction",
        "query_memory_context",
        "resume_pending_process",
        "start_memory_ingestion",
    ]


def test_missing_graph_dependency_produces_tool_error_without_crashing() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "I could not retrieve memory context.",
                "tool": "get_context_package",
                "arguments": {"node_id": "node-marco"},
            }
        ]
    )
    runner = _runner(provider)
    query_context = QueryRetrievalPlanningContext(
        question="What about Marco?",
        conversation=_conversation("What about Marco?"),
    )

    result = runner.run_state(
        AgenticStateInvocation(
            state_id=AgenticStateId.MEMORY_QUERY,
            context_payload=query_context,
            execution_context=AgenticToolExecutionContext(),
        )
    )

    assert result.status == "error"
    assert result.assistant_text == "I could not retrieve memory context."
    assert result.tool_events[0].error["code"] == "missing_dependency"
    assert "graph_service" in result.tool_events[0].error["hint"]


def test_ingestion_handoff_delegates_to_backend_facade() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Routing to ingestion.",
                "tool": "start_memory_ingestion",
                "arguments": {"source_text": "Yesterday I met Marco."},
            }
        ]
    )
    facade = FakeBackendFacade()
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(
        _conversation("Yesterday I met Marco."),
        AgenticToolExecutionContext(
            backend_facade=facade,
            session_id="session-1",
            conversation_id="conversation-1",
            owner_id="owner-1",
        ),
    )

    assert result.status == "ok"
    assert result.final_text == "Memory accepted by backend."
    assert facade.calls[0][1].text == "Yesterday I met Marco."
    assert result.compact_trace[-1]["backend_process"] == "memory_ingestion_precheck"


def test_max_state_transition_limit_prevents_runaway_handoffs() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Routing to memory query.",
                "tool": "query_memory_context",
                "arguments": {"question": "What about Marco?"},
            }
        ]
    )
    runtime = AgenticRuntime(_runner(provider), max_state_transitions=1)

    result = runtime.run(_conversation(), AgenticToolExecutionContext())

    assert result.status == "max_transitions_exceeded"
    assert result.visited_states == [AgenticStateId.CONVERSATION_ENTRY.value]


def test_state_runner_accepts_specialist_context_and_records_tool_events() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Correction proposal prepared.",
                "tool": "build_correction_proposal",
                "arguments": {
                    "correction_text": "Marco was from university.",
                    "target_id": "node-marco",
                    "reason": "The user provided a direct correction.",
                },
            }
        ]
    )
    runner = _runner(provider)
    correction_context = CorrectionIntakeContext(
        correction_text="Marco was from university.",
        conversation=_conversation("Marco was from university."),
        target_hints=["node-marco"],
    )

    result = runner.run_state(
        AgenticStateInvocation(
            state_id=AgenticStateId.CORRECTION_INTAKE,
            context_payload=correction_context,
            execution_context=AgenticToolExecutionContext(),
        )
    )

    assert result.status == "ok"
    assert result.tool_events[0].tool_name == "build_correction_proposal"
    assert result.tool_events[0].data["proposal"]["requires_confirmation"] is True


def test_contradiction_review_question_becomes_pending_process_hint() -> None:
    provider = ScriptedToolCallingProvider(
        [{"content": "This conflicts with the earlier place. Which city was correct?"}]
    )
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(
        _conversation("I met Marco in Milan."),
        AgenticToolExecutionContext(),
        start_state=AgenticStateId.CONTRADICTION_REVIEW,
    )

    assert result.visited_states == [AgenticStateId.CONTRADICTION_REVIEW.value]
    assert result.pending_process_hints[0]["kind"] == "memory_ingestion"
    assert result.pending_process_hints[0]["question"].endswith("Which city was correct?")
