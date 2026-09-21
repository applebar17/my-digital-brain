from __future__ import annotations

import json
from typing import Any

from my_digital_brain.agentic import (
    AgenticMemoryLogExtractionService,
    AgenticPlanningService,
    AgenticReasoningService,
    AgenticRuntime,
    AgenticStateId,
    AgenticStateInvocation,
    AgenticStateRunner,
    AgenticStateRunResult,
    AgenticToolExecutionContext,
    ChannelSessionMetadata,
    ConversationContext,
    EdgeMemoryPlan,
    GraphUpdateContext,
    MemoryIngestionReasoning,
    MemoryLogMemoryPlan,
    MemoryPlanAction,
    MemoryPlanPacket,
    MemoryPlanStep,
    NeutralConversationMessage,
    NodeMemoryPlan,
    NodePlanPacket,
    PlannedRefPacket,
    PlanningPurposeGuidelines,
    PlanningTransformContext,
    PlanningTransformResultContext,
    QueryRetrievalPlanningContext,
    ReasoningCheckpointContext,
    ReasoningPurposeGuidelines,
)
from my_digital_brain.agentic.contexts import MemoryIngestionContext
from my_digital_brain.agentic.enums import MemoryPlanActionType, MemoryPlanningPhase, RefObjectKind
from my_digital_brain.agentic.refs import RefContext, RefEntry
from my_digital_brain.agentic.runtime_memory import (
    MemoryIngestionRuntimeService,
    _unresolved_edge_endpoint_refs,
    _validate_phase_plan_refs,
    _verify_created_action_ref,
)
from my_digital_brain.agentic.runtime_models import AgenticRunResult, AgenticToolEvent
from my_digital_brain.agentic.runtime_state import (
    _has_terminal_tool_error,
    _mark_recovered_tool_attempts,
)
from my_digital_brain.ai.schemas import (
    ChatMessage,
    ProviderCallMetadata,
)
from my_digital_brain.ai.session import (
    LLMCompletionRequest,
    LLMCompletionResult,
    LLMSessionRequest,
    LLMSessionResult,
    LLMSessionRunner,
)
from my_digital_brain.chat.models import AgenticFrame
from my_digital_brain.chat.store import InMemoryChatSessionStore
from my_digital_brain.clarification.contracts import ClarificationPacket
from my_digital_brain.ingestion.contracts import MemoryLogDraftBatch


class ScriptedToolCallingProvider:
    provider_name = "scripted"

    def __init__(
        self,
        steps: list[dict[str, Any]],
        *,
        structured_payloads: list[dict[str, Any]] | None = None,
    ) -> None:
        self.steps = list(steps)
        self.structured_payloads = list(structured_payloads or [])
        self.calls: list[dict[str, Any]] = []
        self.structured_calls: list[LLMSessionRequest] = []
        self.completion_calls = 0
        self.completion_messages: list[list[ChatMessage]] = []

    def run_session(self, request: LLMSessionRequest) -> LLMSessionResult:
        if request.output_schema is not None:
            self.structured_calls.append(request)
        self.calls.append(
            {
                "request": request,
                "toolbox": request.toolbox,
                "tool_names": sorted(request.toolbox.tools_by_name) if request.toolbox else [],
                "max_tool_calls": request.max_tool_calls,
            }
        )
        return LLMSessionRunner(self).run(request)

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        self.completion_calls += 1
        self.completion_messages.append(list(request.messages))
        if request.response_format:
            return LLMCompletionResult(
                assistant_message=ChatMessage(
                    role="assistant",
                    content=json.dumps(self.structured_payloads.pop(0)),
                ),
                metadata=ProviderCallMetadata.fake(model=request.model),
            )
        step = self.steps.pop(0) if self.steps else {"content": ""}
        tool_name = step.get("tool")
        tool_calls = []
        if isinstance(tool_name, str):
            tool_calls = [
                {
                    "id": f"call-{len(self.calls)}",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": _json_arguments(step.get("arguments", {})),
                    },
                }
            ]
        content = step.get("content")
        return LLMCompletionResult(
            assistant_message=ChatMessage(
                role="assistant",
                content=str(content) if content is not None else None,
                tool_calls=tool_calls or None,
            ),
            metadata=ProviderCallMetadata.fake(model=request.model),
        )


def _json_arguments(arguments: object) -> str:
    return json.dumps(arguments if isinstance(arguments, dict) else {}, sort_keys=True)


def test_recovered_tool_attempt_does_not_fail_the_completed_state() -> None:
    events = [
        AgenticToolEvent(
            tool_name="create_person_node",
            status="recoverable_error",
            data={"operation": "create_person_node"},
        ),
        AgenticToolEvent(
            tool_name="create_person_node",
            status="ok",
            data={"operation": "create_person_node"},
        ),
    ]

    _mark_recovered_tool_attempts(events)

    assert events[0].data["recovered_by_later_attempt"] is True
    assert _has_terminal_tool_error(events) is False


def _tool_result_content(result: object) -> str:
    if hasattr(result, "model_dump_json"):
        return result.model_dump_json(exclude_none=True)
    return json.dumps(result, default=str)


def _memory_ingestion_structured_payloads() -> list[dict[str, Any]]:
    node_action = {
        "action_id": "node_action_0001",
        "action_type": "create_node",
        "target_refs": ["node_new_0001"],
        "rationale": "Create Marco as a person candidate.",
        "payload": {"created_refs": ["node_new_0001"]},
    }
    return [
        {
            "highlights": {
                "nodes": {"persons": "Marco is the main person."},
                "logs": ["The user clarified Marco was from university."],
                "edges": {"relationships": "University context may matter."},
            },
            "possible_aliases": [{"main_mention": "Marco", "aliases": ["Marco from university"]}],
            "planning_guidance": "Plan nodes, then memories, then edges.",
        },
        {
            "summary": "Plan Marco as a node.",
            "steps": [
                {
                    "step_id": "node_step_0001",
                    "phase": "nodes",
                    "execution_mode": "sequential",
                    "actions": [node_action],
                }
            ],
            "node_plan_packet": {
                "planned_refs": [
                    {
                        "ref": "node_new_0001",
                        "object_kind": "node",
                        "label": "Person",
                        "name": "Marco",
                        "aliases": ["Marco from university"],
                    }
                ],
                "summary": "Marco is available as node_new_0001 for memory planning.",
            },
        },
        {
            "summary": "Plan one compact MemoryLog.",
            "steps": [
                {
                    "step_id": "memory_step_0001",
                    "phase": "memory_logs",
                    "execution_mode": "parallel",
                    "actions": [
                        {
                            "action_id": "memory_action_0001",
                            "action_type": "create_memory_log",
                            "target_refs": ["memory_new_0001", "node_new_0001"],
                            "rationale": "Create one clarification memory.",
                            "payload": {"created_refs": ["memory_new_0001"]},
                        }
                    ],
                }
            ],
            "memory_plan_packet": {
                "planned_refs": [
                    {
                        "ref": "memory_new_0001",
                        "object_kind": "memory",
                        "label": "MemoryLog",
                        "summary": "Marco was from university, not work.",
                    }
                ],
                "host_refs": ["node_new_0001"],
                "involved_refs": ["node_new_0001"],
                "summary": "memory_new_0001 can anchor edge planning.",
            },
        },
        {
            "summary": "Plan one ref-based edge.",
            "steps": [
                {
                    "step_id": "edge_step_0001",
                    "phase": "edges",
                    "execution_mode": "sequential",
                    "actions": [
                        {
                            "action_id": "edge_action_0001",
                            "action_type": "create_relationship",
                            "target_refs": ["node_new_0001"],
                            "rationale": "Link the person to the university context.",
                            "payload": {
                                "from_ref": "node_new_0001",
                                "to_ref": "node_0001",
                                "created_refs": ["edge_new_0001"],
                            },
                        }
                    ],
                }
            ],
        },
    ]


class FakeGraphService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.mutations: list[str] = []

    def get_node(self, node_id: str):
        self.calls.append(("get_node", node_id))
        from my_digital_brain.graph.models import NodeSearchResult

        return NodeSearchResult(
            label="Person",
            labels=["Person"],
            properties={"id": node_id, "display_name": "Marco"},
        )

    def upsert_node(self, label: str, properties: dict[str, Any]):
        self.mutations.append(f"upsert_node:{label}")
        from my_digital_brain.graph.models import NodeSearchResult

        return NodeSearchResult(
            label=label,
            labels=[label],
            properties={"id": f"{label.lower()}-1", **properties},
        )

    def upsert_relationship(
        self,
        relationship_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any],
    ):
        self.mutations.append(f"upsert_relationship:{relationship_type}")
        from my_digital_brain.graph.models import RelationshipResult

        return RelationshipResult(
            type=relationship_type,
            from_id=from_id,
            to_id=to_id,
            properties={"id": f"{from_id}:{relationship_type}:{to_id}", **properties},
        )

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


def _runner(provider: ScriptedToolCallingProvider) -> AgenticStateRunner:
    return AgenticStateRunner(provider=provider)


def _existing_graph_ref_context() -> RefContext:
    context = RefContext(session_id="ingestion-test")
    context.add_entry(
        RefEntry(
            ref="node_0001",
            object_kind=RefObjectKind.NODE,
            backend_id="node-backend-1",
            label="Place",
            name="University",
        )
    )
    return context


def _conversation(text: str = "What do I remember about Marco?") -> ConversationContext:
    return ConversationContext(
        current_message=NeutralConversationMessage.user(text),
        channel_metadata=ChannelSessionMetadata(
            channel="web",
            conversation_id="conversation-1",
            owner_id="owner-1",
            session_id="session-1",
        ),
    )


def test_conversation_entry_without_tool_call_returns_terminal_assistant_response() -> None:
    provider = ScriptedToolCallingProvider([{"content": "I can help you store or query memories."}])
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(_conversation("hello"), AgenticToolExecutionContext())

    assert result.status == "ok"
    assert result.final_text == "I can help you store or query memories."
    assert result.visited_states == [AgenticStateId.CONVERSATION_ENTRY.value]
    assert result.state_results[0].terminal is True
    prompt_payload = provider.calls[0]["request"].messages[0].content
    assert "channel_metadata" not in str(prompt_payload)
    assert provider.calls[0]["tool_names"] == ["ingest_memory", "query_memory"]


def test_conversation_entry_query_tool_runs_memory_query_child_frame() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Routing to memory query.",
                "tool": "query_memory",
                "arguments": {
                    "question": "What do I remember about Marco?",
                    "seed_id": "node-marco",
                    "desired_view": None,
                    "metadata": {},
                },
            },
            {"content": "Marco is a university friend."},
        ]
    )
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(_conversation(), AgenticToolExecutionContext())

    assert result.status == "ok"
    assert result.visited_states == [AgenticStateId.CONVERSATION_ENTRY.value]
    event = result.state_results[0].tool_events[0]
    assert event.tool_name == "query_memory"
    assert event.status == "ok"
    assert event.data["child_state_id"] == AgenticStateId.MEMORY_QUERY.value
    assert event.data["summary"] == "Marco is a university friend."
    assert provider.calls[0]["tool_names"] == ["ingest_memory", "query_memory"]
    assert provider.calls[1]["tool_names"] == [
        "get_context_package",
        "get_entity_detail",
        "get_latest_contact_details",
        "get_map_view",
        "get_memories_involving_node",
        "get_neighborhood_view",
        "get_target_evidence",
        "get_timeline",
    ]


def test_conversation_entry_ingest_tool_runs_memory_ingestion_child_frame() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {"content": "Routing to ingestion.", "tool": "ingest_memory", "arguments": {}},
            {
                "content": "Creating Marco.",
                "tool": "create_person_node",
                "arguments": {
                    "person": {
                        "display_name": "Marco Rossi",
                        "description": "A university contact mentioned by the user.",
                    }
                },
            },
            {"content": "Node action complete."},
            {
                "content": "Creating the memory log.",
                "tool": "create_memory_log",
                "arguments": {
                    "memory_log": {
                        "title": "Marco's university connection",
                        "log_text": "Marco was from university, not work.",
                        "host_target_ids": ["node_new_0001"],
                        "primary_host_target_id": "node_new_0001",
                        "involved_target_ids": ["node_new_0001"],
                    }
                },
            },
            {"content": "Memory action complete."},
            {
                "content": "Linking Marco to the university.",
                "tool": "upsert_graph_relationship",
                "arguments": {
                    "relationship": {
                        "relationship_type": "RELATIONSHIP_WITH",
                        "from_id": "node_new_0001",
                        "to_id": "node_0001",
                        "relationship_kind": "university connection",
                    }
                },
            },
            {"content": "Edge action complete."},
            {"content": "I've saved that Marco was from university."},
        ],
        structured_payloads=_memory_ingestion_structured_payloads(),
    )
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(
        _conversation("Marco was from university, not work."),
        AgenticToolExecutionContext(
            graph_service=FakeGraphService(),
            ref_context=_existing_graph_ref_context(),
        ),
    )

    assert result.status == "ok"
    assert result.visited_states == [AgenticStateId.CONVERSATION_ENTRY.value]
    event = result.state_results[0].tool_events[0]
    assert event.tool_name == "ingest_memory"
    assert event.status == "ok"
    assert event.data["child_state_id"] == AgenticStateId.MEMORY_INGESTION.value
    assert (
        event.data["summary"]
        == "Memory ingestion planning completed through nodes, memory_logs, and edges."
    )
    assert [call.output_schema.__name__ for call in provider.structured_calls] == [
        "MemoryIngestionReasoning",
        "NodeMemoryPlan",
        "MemoryLogMemoryPlan",
        "EdgeMemoryPlan",
    ]


def test_conversation_entry_has_no_pending_process_surface() -> None:
    provider = ScriptedToolCallingProvider([{"content": "Handled normally."}])
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(_conversation("I am not sure"), AgenticToolExecutionContext())

    assert result.visited_states == [AgenticStateId.CONVERSATION_ENTRY.value]
    assert provider.calls[0]["tool_names"] == ["ingest_memory", "query_memory"]


def test_missing_graph_dependency_produces_tool_error_without_crashing() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "I could not retrieve memory context.",
                "tool": "get_context_package",
                "arguments": {"node_id": "node-marco"},
            },
            {"content": "I could not retrieve memory context."},
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


def test_clarification_handoff_uses_structured_child_state() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Handing off the identity doubt.",
                "tool": "ask_clarification",
                "arguments": {
                    "doubts": [
                        {
                            "doubt_id": "DOUBT_001",
                            "doubt": "Marco has two possible graph matches.",
                            "refs": ["node_0001", "node_0002"],
                            "missing_information": "Which context identifies Marco.",
                            "why_blocking": "The target is ambiguous.",
                            "evidence_refs": ["memory_0001"],
                        }
                    ]
                },
            },
            {"content": "I need one detail before I can continue."},
        ],
        structured_payloads=[
            {
                "entries": [
                    {
                        "doubt_id": "DOUBT_001",
                        "status": "unresolved",
                        "remaining_uncertainty": "No user answer yet.",
                    }
                ],
                "summary": "The doubt remains unresolved.",
            }
        ],
    )
    runtime = AgenticRuntime(_runner(provider))
    refs = RefContext(session_id="session-1")
    refs.register_existing("person-marco-1", RefObjectKind.NODE, label="Person", name="Marco")
    refs.register_existing("person-marco-2", RefObjectKind.NODE, label="Person", name="Marco")
    refs.register_existing(
        "memory-1",
        RefObjectKind.MEMORY,
        label="MemoryLog",
        name="Identity context",
    )
    result = runtime.run(
        _conversation("Marco has two possible identities."),
        AgenticToolExecutionContext(
            session_id="session-1",
            conversation_id="conversation-1",
            application_user_id="account-user-1",
            graph_owner_id="person:owner",
            agentic_runtime=runtime,
            ref_context=refs,
        ),
        start_state=AgenticStateId.GRAPH_UPDATE,
        start_payload=GraphUpdateContext(
            source_text="Marco has two possible identities.",
            conversation=_conversation("Marco has two possible identities."),
            ref_context=refs,
        ),
    )

    assert result.status == "ok"
    event = result.state_results[0].tool_events[0]
    assert event.tool_name == "ask_clarification"
    assert event.status == "ok"
    assert event.data["clarification_report"]["entries"][0]["status"] == "unresolved"


def test_resumed_child_report_reaches_parent_invoker_tool_output() -> None:
    provider = ScriptedToolCallingProvider([{"content": "Create Amos Vignaroli."}])
    runtime = AgenticRuntime(_runner(provider))
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel="web",
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    conversation = _conversation("Remember that I met Amos.")
    report = {
        "entries": [
            {
                "doubt_id": "DOUBT_001",
                "status": "resolved",
                "user_answers": ["Amos Vignaroli"],
                "clarified_values": {"display_name": "Amos Vignaroli"},
                "evidence_refs": ["CANDIDATE_PERSON_001"],
            }
        ],
        "summary": "Amos was identified as Amos Vignaroli.",
    }
    parent = AgenticFrame(
        frame_id="parent-frame-1",
        session_id=session.session_id,
        state_id=AgenticStateId.GRAPH_UPDATE.value,
        status="interrupted",
        messages=[
            {"role": "system", "content": "Graph update instructions."},
            {"role": "user", "content": "Remember that I met Amos."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call-clarification",
                        "type": "function",
                        "function": {
                            "name": "ask_clarification",
                            "arguments": "{}",
                        },
                    }
                ],
            },
        ],
        context_payload={"conversation": conversation.model_dump(mode="json")},
        active_tool_call_id="call-clarification",
        active_tool_name="ask_clarification",
    )
    child = AgenticFrame(
        frame_id="child-frame-1",
        session_id=session.session_id,
        state_id=AgenticStateId.CLARIFICATION_AGENT.value,
        status="completed",
        parent_frame_id=parent.frame_id,
        parent_tool_call_id="call-clarification",
        metadata={"clarification_report": report},
    )
    store.save_agentic_frame(session.session_id, parent)
    execution_context = AgenticToolExecutionContext(
        chat_store=store,
        session_id=session.session_id,
        frame_id=parent.frame_id,
        agentic_runtime=runtime,
        conversation_context=conversation,
    )

    result = runtime._resume_parent_frame(
        parent,
        child_frame=child,
        child_result=AgenticStateRunResult(
            state_id=AgenticStateId.CLARIFICATION_AGENT,
            status="ok",
        ),
        execution_context=execution_context,
    )

    assert result.status == "ok"
    assert result.metadata["clarification_report"] == report
    assert result.metadata["resolved_clarifications"][0]["clarified_values"] == {
        "display_name": "Amos Vignaroli"
    }
    tool_message = provider.calls[0]["request"].messages[-1]
    assert tool_message.role == "tool"
    assert "Amos Vignaroli" in tool_message.content
    assert "clarified_values" in tool_message.content


def test_child_reuses_provider_parent_tool_call_id(monkeypatch) -> None:
    runtime = AgenticRuntime(_runner(ScriptedToolCallingProvider([])))
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel="web",
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    parent_context = AgenticToolExecutionContext(
        chat_store=store,
        session_id=session.session_id,
        state_id=AgenticStateId.PLANNING_CHECKPOINT.value,
        frame_id="parent-frame-1",
        current_tool_call_id="openai-call-1",
        current_payload={"purpose": "test"},
    )
    captured: dict[str, AgenticToolExecutionContext] = {}

    def fake_run(
        _runtime,
        _conversation_context,
        execution_context,
        start_state=None,
        start_payload=None,
    ) -> AgenticRunResult:
        captured["child"] = execution_context
        packet = ClarificationPacket(
            frame_id=execution_context.frame_id or "child-frame-1",
            tool_call_id="ask-call-1",
            tool_name="ask_text",
            origin_state_id=AgenticStateId.CLARIFICATION_AGENT.value,
            reason="Need one detail.",
            questions=[
                {
                    "question": "What is the surname?",
                    "kind": "missing_attribute",
                    "response_mode": "free_text",
                }
            ],
        )
        store.save_agentic_frame(
            session.session_id,
            AgenticFrame(
                frame_id=execution_context.frame_id or "child-frame-1",
                session_id=session.session_id,
                state_id=AgenticStateId.CLARIFICATION_AGENT.value,
                status="interrupted",
                parent_frame_id=execution_context.parent_frame_id,
                parent_tool_call_id=execution_context.parent_tool_call_id,
                active_tool_call_id="ask-call-1",
                active_tool_name="ask_text",
                clarification_packet=packet,
            ),
        )
        return AgenticRunResult(
            status="interrupted",
            final_text="I need one detail.",
            interruption={
                "frame_id": execution_context.frame_id,
                "state_id": AgenticStateId.CLARIFICATION_AGENT.value,
                "tool_call_id": "ask-call-1",
                "tool_name": "ask_text",
                "clarification_packet": packet.model_dump(mode="json"),
            },
        )

    monkeypatch.setattr(AgenticRuntime, "run", fake_run)
    result = runtime.run_child_frame(
        parent_execution_context=parent_context,
        conversation_context=_conversation("Remember this."),
        child_state=AgenticStateId.CLARIFICATION_AGENT,
        child_payload={},
        tool_name="ask_clarification",
    )

    saved_parent = store.get_agentic_frame("parent-frame-1")
    saved_child = store.get_agentic_frame(captured["child"].frame_id or "")
    assert result.status == "pending"
    assert saved_parent.active_tool_call_id == "openai-call-1"
    assert captured["child"].parent_tool_call_id == "openai-call-1"
    assert saved_child.parent_tool_call_id == "openai-call-1"


def test_internal_child_does_not_invent_provider_tool_call_id() -> None:
    runtime = AgenticRuntime(_runner(ScriptedToolCallingProvider([])))
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel="web",
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    parent_context = AgenticToolExecutionContext(
        chat_store=store,
        session_id=session.session_id,
        state_id=AgenticStateId.MEMORY_INGESTION.value,
        frame_id="internal-parent-frame",
        current_payload={"source_text": "Remember this."},
    )

    result = runtime._persist_waiting_child_frame(
        parent_context,
        _conversation("Remember this."),
        child_result=AgenticRunResult(
            status="interrupted",
            final_text="I need one detail.",
            interruption={"frame_id": "clarification-frame"},
        ),
        tool_name="run_memory_creation",
    )

    saved_parent = store.get_agentic_frame("internal-parent-frame")
    assert result["status"] == "waiting_child"
    assert saved_parent.active_tool_call_id is None
    assert saved_parent.messages == []
    assert not any(
        call.get("id", "").startswith("child-")
        for message in saved_parent.messages
        for call in message.get("tool_calls", [])
    )


def test_resume_frame_continues_backend_ingestion_without_provider_call_id(monkeypatch) -> None:
    runtime = AgenticRuntime(_runner(ScriptedToolCallingProvider([])))
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel="web",
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    conversation = _conversation("Remember this.")
    payload = MemoryIngestionContext(conversation=conversation)
    parent = AgenticFrame(
        frame_id="internal-parent-frame",
        session_id=session.session_id,
        state_id=AgenticStateId.MEMORY_INGESTION.value,
        status="waiting_child",
        context_payload={
            "conversation": conversation.model_dump(mode="json"),
            "current_payload": payload.model_dump(mode="json"),
        },
        metadata={
            "internal_continuation": {
                "kind": "memory_ingestion",
                "phase": "memory_logs",
                "action_id": "memory_action_0001",
                "payload": payload.model_dump(mode="json"),
            }
        },
    )
    child = AgenticFrame(
        frame_id="clarification-frame",
        session_id=session.session_id,
        state_id=AgenticStateId.CLARIFICATION_AGENT.value,
        status="completed",
        parent_frame_id=parent.frame_id,
        metadata={"resolved_clarifications": [{"doubt_id": "doubt-1"}]},
    )
    store.save_agentic_frame(session.session_id, parent)
    execution_context = AgenticToolExecutionContext(
        chat_store=store,
        session_id=session.session_id,
        frame_id=parent.frame_id,
        agentic_runtime=runtime,
    )

    def fake_memory_run(_self, resumed_payload, resumed_context, resumed_conversation):
        assert resumed_context.frame_id == parent.frame_id
        assert resumed_context.current_tool_call_id is None
        assert resumed_payload.resolved_clarifications == [{"doubt_id": "doubt-1"}]
        assert resumed_conversation.current_message.content == "Remember this."
        return AgenticRunResult(
            final_text="Memory ingestion completed.",
            status="ok",
            metadata={
                "structured_output": {"summary": "Memory ingestion completed."},
                "resolved_clarifications": resumed_payload.resolved_clarifications,
            },
        )

    monkeypatch.setattr(
        "my_digital_brain.agentic.runtime_memory.MemoryIngestionRuntimeService.run",
        fake_memory_run,
    )
    result = runtime._resume_parent_frame(
        parent,
        child_frame=child,
        child_result=AgenticStateRunResult(
            state_id=AgenticStateId.CLARIFICATION_AGENT,
            status="ok",
            metadata={"resolved_clarifications": [{"doubt_id": "doubt-1"}]},
        ),
        execution_context=execution_context,
    )

    assert result.status == "ok"
    assert result.final_text == "Memory ingestion completed."
    assert store.get_agentic_frame(parent.frame_id).status == "completed"


def test_memory_ingestion_resume_reuses_existing_reasoning(monkeypatch) -> None:
    """A resumed phase must not lose the reasoning artifact from the first pass."""

    monkeypatch.setattr(
        MemoryIngestionRuntimeService,
        "_execute_memory_plan_actions",
        lambda *args, **kwargs: None,
    )
    reasoning = MemoryIngestionReasoning(planning_guidance="Keep the existing context coherent.")

    def phase_step(phase: MemoryPlanningPhase) -> MemoryPlanStep:
        return MemoryPlanStep(
            step_id=f"{phase.value}_step",
            phase=phase,
            actions=[MemoryPlanAction(action_type=MemoryPlanActionType.CREATE_NODE)],
        )

    payload = MemoryIngestionContext(
        conversation=_conversation("Remember Marco."),
        reasoning=reasoning,
        node_plan=NodeMemoryPlan(
            summary="Nodes already planned.",
            steps=[phase_step(MemoryPlanningPhase.NODES)],
            node_plan_packet=NodePlanPacket(summary="No new nodes are required."),
        ),
        memory_plan=MemoryLogMemoryPlan(
            summary="Memory logs already planned.",
            steps=[phase_step(MemoryPlanningPhase.MEMORY_LOGS)],
            memory_plan_packet=MemoryPlanPacket(summary="No new memory logs are required."),
        ),
        edge_plan=EdgeMemoryPlan(
            summary="Edges already planned.",
            steps=[phase_step(MemoryPlanningPhase.EDGES)],
        ),
    )

    result = MemoryIngestionRuntimeService(runtime=object()).run(
        payload,
        AgenticToolExecutionContext(),
        payload.conversation,
    )

    assert result.status == "ok"
    assert result.metadata["structured_output"]["plan"]["metadata"]["reasoning"] == (
        reasoning.model_dump(mode="json", exclude_none=True)
    )


def test_phase_actions_bind_planned_outputs_and_defer_unresolved_edges() -> None:
    refs = RefContext(session_id="handoff-test")
    plan = NodeMemoryPlan(
        summary="Create Marco.",
        node_plan_packet=NodePlanPacket(
            planned_refs=[
                PlannedRefPacket(
                    ref="node_new_marco",
                    object_kind=RefObjectKind.NODE,
                    label="Person",
                    name="Marco",
                )
            ],
            summary="Marco is planned.",
        ),
        steps=[
            MemoryPlanStep(
                step_id="node_step_001",
                phase=MemoryPlanningPhase.NODES,
                actions=[
                    MemoryPlanAction(
                        action_type=MemoryPlanActionType.CREATE_NODE,
                        target_refs=["node_new_marco"],
                    )
                ],
            )
        ],
    )

    _validate_phase_plan_refs(plan, refs)
    refs.register_proposed("node_new_marco", RefObjectKind.NODE)
    action = plan.steps[0].actions[0]
    assert _verify_created_action_ref(action, refs, succeeded=True) is not None

    refs.resolve_backend_id("node_new_marco", "graph-marco", status="created")
    assert _verify_created_action_ref(action, refs, succeeded=True) is None

    edge = MemoryPlanAction(
        action_type=MemoryPlanActionType.CREATE_RELATIONSHIP,
        payload={"from_ref": "node_new_marco", "to_ref": "node_missing"},
    )
    assert _unresolved_edge_endpoint_refs(edge, refs) == ["node_missing"]


def test_memory_ingestion_returns_a_required_phase_error_to_its_invoker(monkeypatch) -> None:
    phases: list[MemoryPlanningPhase] = []

    def execute(_self, *_args, phase: MemoryPlanningPhase, **_kwargs):
        phases.append(phase)
        return AgenticRunResult(
            final_text="MemoryLog creation requires at least one host target.",
            state_results=[
                AgenticStateRunResult(
                    state_id=AgenticStateId.MEMORY_CREATION,
                    status="error",
                )
            ],
            status="error",
        )

    monkeypatch.setattr(MemoryIngestionRuntimeService, "_execute_memory_plan_actions", execute)
    payload = MemoryIngestionContext(
        conversation=_conversation("Remember Marco."),
        reasoning=MemoryIngestionReasoning(planning_guidance="Keep the context coherent."),
        node_plan=NodeMemoryPlan(
            summary="Nodes planned.",
            steps=[
                MemoryPlanStep(
                    step_id="node_step_001",
                    phase=MemoryPlanningPhase.NODES,
                    actions=[MemoryPlanAction(action_type=MemoryPlanActionType.CREATE_NODE)],
                )
            ],
            node_plan_packet=NodePlanPacket(summary="Nodes ready."),
        ),
        memory_plan=MemoryLogMemoryPlan(
            summary="Memory logs planned.",
            steps=[
                MemoryPlanStep(
                    step_id="memory_step_001",
                    phase=MemoryPlanningPhase.MEMORY_LOGS,
                    actions=[MemoryPlanAction(action_type=MemoryPlanActionType.CREATE_MEMORY_LOG)],
                )
            ],
            memory_plan_packet=MemoryPlanPacket(summary="Memory logs ready."),
        ),
        edge_plan=EdgeMemoryPlan(
            summary="Edges planned.",
            steps=[
                MemoryPlanStep(
                    step_id="edge_step_001",
                    phase=MemoryPlanningPhase.EDGES,
                    actions=[MemoryPlanAction(action_type=MemoryPlanActionType.UPDATE_NODE)],
                )
            ],
        ),
    )

    result = MemoryIngestionRuntimeService(runtime=object()).run(
        payload,
        AgenticToolExecutionContext(),
        payload.conversation,
    )

    assert result.status == "error"
    assert result.metadata["failed_phase"] == MemoryPlanningPhase.NODES.value
    assert result.metadata["requires_invoker_response"] is True
    assert phases == [MemoryPlanningPhase.NODES]
    assert "Review the returned diagnostic" in (result.final_text or "")


def test_ingest_memory_tool_uses_child_frame_without_legacy_facade() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {"content": "Routing to ingestion.", "tool": "ingest_memory", "arguments": {}},
            {
                "content": "Creating Marco.",
                "tool": "create_person_node",
                "arguments": {
                    "person": {
                        "display_name": "Marco Rossi",
                        "description": "A university contact mentioned by the user.",
                    }
                },
            },
            {"content": "Node action complete."},
            {
                "content": "Creating the memory log.",
                "tool": "create_memory_log",
                "arguments": {
                    "memory_log": {
                        "title": "Marco's university connection",
                        "log_text": "Marco was from university, not work.",
                        "host_target_ids": ["node_new_0001"],
                        "primary_host_target_id": "node_new_0001",
                        "involved_target_ids": ["node_new_0001"],
                    }
                },
            },
            {"content": "Memory action complete."},
            {
                "content": "Linking Marco to the university.",
                "tool": "upsert_graph_relationship",
                "arguments": {
                    "relationship": {
                        "relationship_type": "RELATIONSHIP_WITH",
                        "from_id": "node_new_0001",
                        "to_id": "node_0001",
                        "relationship_kind": "university connection",
                    }
                },
            },
            {"content": "Edge action complete."},
            {"content": "I've saved that Marco was from university."},
        ],
        structured_payloads=_memory_ingestion_structured_payloads(),
    )
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(
        _conversation("Yesterday I met Marco."),
        AgenticToolExecutionContext(
            graph_service=FakeGraphService(),
            session_id="session-1",
            conversation_id="conversation-1",
            application_user_id="account-user-1",
            graph_owner_id="person:owner",
            ref_context=_existing_graph_ref_context(),
        ),
    )

    assert result.status == "ok"
    assert result.state_results[0].tool_events[0].tool_name == "ingest_memory"
    assert result.state_results[0].tool_events[0].data["child_state_id"] == (
        AgenticStateId.MEMORY_INGESTION.value
    )
    assert "state_results" not in result.state_results[0].tool_events[0].data


def test_child_frames_do_not_use_handoff_state_switching() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Routing to memory query.",
                "tool": "query_memory",
                "arguments": {
                    "question": "What about Marco?",
                    "seed_id": None,
                    "desired_view": None,
                    "metadata": {},
                },
            },
            {"content": "Memory query complete."},
        ]
    )
    runtime = AgenticRuntime(_runner(provider), max_state_transitions=1)

    result = runtime.run(_conversation(), AgenticToolExecutionContext())

    assert result.status == "ok"
    assert result.visited_states == [AgenticStateId.CONVERSATION_ENTRY.value]
    assert result.state_results[0].tool_events[0].data["visited_states"] == [
        AgenticStateId.MEMORY_QUERY.value,
    ]


def test_state_runner_accepts_specialist_context_and_records_tool_events() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Graph update applied.",
                "tool": "create_memory_log",
                "arguments": {
                    "memory_log": {
                        "title": "Marco's university connection",
                        "log_text": "Marco was from university.",
                        "host_target_ids": ["node-marco"],
                        "primary_host_target_id": None,
                        "involved_target_ids": [],
                        "relationship_context_target_ids": [],
                        "media_refs": [],
                        "log_kind": "correction",
                        "source_kind": "chat",
                        "happened_at": None,
                    }
                },
            }
        ]
    )
    runner = _runner(provider)
    graph_update_context = GraphUpdateContext(
        source_text="Marco was from university.",
        conversation=_conversation("Marco was from university."),
        guidelines="Apply as correction.",
        desired_work="correct_or_update_memory_graph",
        target_ids=["node-marco"],
    )
    graph = FakeGraphService()

    result = runner.run_state(
        AgenticStateInvocation(
            state_id=AgenticStateId.GRAPH_UPDATE,
            context_payload=graph_update_context,
            execution_context=AgenticToolExecutionContext(graph_service=graph),
        )
    )

    assert result.status == "ok"
    assert result.tool_events[0].tool_name == "create_memory_log"
    assert result.tool_events[0].data["created_refs"]
    assert "upsert_node:MemoryLog" in graph.mutations


def test_reasoning_checkpoint_service_runs_structured_state() -> None:
    provider = ScriptedToolCallingProvider(
        [],
        structured_payloads=[
            {
                "checkpoint_id": "checkpoint-1",
                "purpose_id": "memory_storage_precheck",
                "summary": "The memory contains an owner relationship to Alessia.",
                "insights": [
                    {
                        "insight_type": "relationship_intent",
                        "summary": "The phrase 'my girlfriend' expresses a relationship.",
                        "evidence_text": "Alessia is my girlfriend",
                    }
                ],
                "entity_understandings": [
                    {
                        "mention_text": "Alessia",
                        "interpretation": "Person anchor mentioned by the user.",
                        "should_be_node": True,
                        "possible_node_type": "Person",
                    }
                ],
                "storage_recommendations": [
                    {
                        "subject": "Alessia relationship",
                        "recommendation_type": "create_relationship_context",
                        "reason": "The user described a meaningful personal relationship.",
                        "guardrails": ["Backend must decide owner/self graph representation."],
                    }
                ],
            }
        ],
    )
    service = AgenticReasoningService(_runner(provider))
    context = ReasoningCheckpointContext(
        checkpoint_id="checkpoint-1",
        purpose=ReasoningPurposeGuidelines(
            purpose_id="memory_storage_precheck",
            goal="Identify owner references and node-versus-metadata choices.",
            focus_areas=["owner relationship", "node versus metadata"],
        ),
        conversation=_conversation("Alessia is my girlfriend."),
        input_context={"source_text": "Alessia is my girlfriend."},
        timezone="Europe/Rome",
    )

    result = service.reason(context, AgenticToolExecutionContext())

    assert result.status == "ok"
    assert result.state_id == AgenticStateId.REASONING_CHECKPOINT.value
    assert result.structured_output is not None
    assert result.structured_output["purpose_id"] == "memory_storage_precheck"
    assert result.structured_output["insights"][0]["insight_type"] == "relationship_intent"
    structured_call = provider.structured_calls[0]
    assert structured_call.context.purpose == "reasoning_checkpoint"
    assert structured_call.output_schema.__name__ == "ReasoningCheckpointResultContext"
    assert "Runtime context:" not in structured_call.system_prompt
    assert "timezone: Europe/Rome" not in structured_call.system_prompt
    assert structured_call.messages[-1].role == "user"
    assert structured_call.messages[-1].content == "Alessia is my girlfriend."
    assert "Process context:" not in structured_call.system_prompt
    assert "# Context" in structured_call.system_prompt
    assert "checkpoint_id" not in structured_call.system_prompt
    assert "source_text" not in structured_call.system_prompt
    assert "owner relationship" in structured_call.system_prompt
    assert "node versus metadata" in structured_call.system_prompt
    assert context.purpose.focus_areas == [
        "owner relationship",
        "node versus metadata",
    ]


def test_planning_checkpoint_service_runs_structured_state() -> None:
    provider = ScriptedToolCallingProvider(
        [],
        structured_payloads=[
            {
                "planning_id": "planning-1",
                "purpose_id": "entity_ingestion_planning",
                "summary": "Plan one entity action for Matteo Mercoldi.",
                "actions": [
                    {
                        "action_ref": "ACTION_001",
                        "goal": "Extract Matteo Mercoldi as one person candidate.",
                        "action_kind": "extract_entity",
                        "target_refs": ["NODE_000001"],
                        "evidence_text": "Merc is Matteo Mercoldi.",
                    }
                ],
            }
        ],
    )
    service = AgenticPlanningService(_runner(provider))
    context = PlanningTransformContext(
        planning_id="planning-1",
        purpose=PlanningPurposeGuidelines(
            purpose_id="entity_ingestion_planning",
            goal="Plan entity extraction without relationships.",
            focus_areas=["aliases", "duplicate hints"],
        ),
        input_context={
            "source_text": "Merc is Matteo Mercoldi.",
            "graph_context_view": {"aliases": ["Merc -> Matteo Mercoldi"]},
        },
        reasoning_artifact={
            "summary": "Merc is a nickname for Matteo Mercoldi.",
        },
        timezone="Europe/Rome",
    )

    result = service.plan(context, output_schema=PlanningTransformResultContext)

    assert result.status == "ok"
    assert result.state_id == AgenticStateId.PLANNING_CHECKPOINT.value
    assert result.structured_output is not None
    assert result.structured_output["purpose_id"] == "entity_ingestion_planning"
    assert result.structured_output["actions"][0]["action_ref"] == "ACTION_001"
    structured_call = provider.structured_calls[0]
    assert structured_call.context.purpose == "planning_checkpoint"
    assert structured_call.output_schema.__name__ == "PlanningTransformResultContext"
    assert "Runtime context:" not in structured_call.system_prompt
    assert "timezone: Europe/Rome" not in structured_call.system_prompt
    assert len(structured_call.messages) == 1
    assert structured_call.messages[0].role == "user"
    assert structured_call.messages[0].content == "Merc is Matteo Mercoldi."
    assert "Process context:" not in structured_call.system_prompt
    assert "# Context" in structured_call.system_prompt
    assert "planning_id" not in structured_call.system_prompt
    assert "source_text" not in structured_call.system_prompt
    assert "PlanningTransformResultContext" not in structured_call.system_prompt


def test_memory_log_extraction_service_runs_dedicated_state() -> None:
    provider = ScriptedToolCallingProvider(
        [],
        structured_payloads=[
            {
                "candidates": [
                    {
                        "local_ref": "MEMORY_LOG_001",
                        "title": "Merc at the barbeque",
                        "log_text": "Merc came to the barbeque.",
                        "host_refs": [
                            {
                                "target_ref": "CANDIDATE_PERSON_001",
                                "primary": True,
                            }
                        ],
                        "evidence": [
                            {"evidence_text": "Merc came to the barbeque."},
                        ],
                    }
                ]
            }
        ],
    )
    service = AgenticMemoryLogExtractionService(_runner(provider))
    context = PlanningTransformContext(
        purpose=PlanningPurposeGuidelines(
            purpose_id="memory_log_ingestion_extraction",
            goal="Extract a backend-facing MemoryLog draft from one planned target.",
        ),
        input_context={
            "planning_scope": "memory_log_extraction",
            "source_text": "Merc came to the barbeque.",
            "model_user_message": (
                "Ingest this memory-log planning action.\n\n"
                "```json\n"
                '{"expected_local_ref":"MEMORY_LOG_001"}\n'
                "```"
            ),
            "planning_action": {
                "goal": "Create one log.",
                "memory_logs": [{"local_ref": "MEMORY_LOG_001"}],
            },
            "planned_memory_log": {"local_ref": "MEMORY_LOG_001"},
            "expected_local_ref": "MEMORY_LOG_001",
        },
        timezone="Europe/Rome",
    )

    result = service.extract(context, output_schema=MemoryLogDraftBatch)

    assert result.status == "ok"
    assert result.state_id == AgenticStateId.MEMORY_LOG_EXTRACTION.value
    structured_call = provider.structured_calls[0]
    assert structured_call.context.purpose == "memory_log_extraction"
    assert structured_call.output_schema.__name__ == "MemoryLogDraftBatch"
    assert "memory-log ingestor" in structured_call.system_prompt
    assert "planning_checkpoint" not in structured_call.system_prompt
    assert len(structured_call.messages) == 2
    assert structured_call.messages[0].role == "user"
    assert structured_call.messages[0].content == "Merc came to the barbeque."
    assert structured_call.messages[-1].role == "user"
    assert "expected_local_ref" in structured_call.messages[-1].content
    assert "source_text" not in structured_call.messages[-1].content


def test_contradiction_review_question_becomes_clarification_intent() -> None:
    provider = ScriptedToolCallingProvider(
        [{"content": "Review support complete."}],
        structured_payloads=[
            {
                "judge_request_id": "judge-1",
                "intent": "needs_clarification",
                "decision": "needs_clarification",
                "severity": "high",
                "reason": "The same event appears to have two mutually exclusive places.",
                "graph_action": "ask_user",
                "clarification_question": "Was the meeting in Milan or Turin?",
                "affected_refs": ["NODE_000001"],
                "source_refs": ["SOURCE_000001"],
            }
        ],
    )
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(
        _conversation("I met Marco in Milan."),
        AgenticToolExecutionContext(),
        start_state=AgenticStateId.CONTRADICTION_REVIEW,
    )

    assert result.visited_states == [
        AgenticStateId.CONTRADICTION_REVIEW.value,
        AgenticStateId.CONTRADICTION_REVIEW.value,
    ]
    assert result.metadata["contradiction_intent"] == "needs_clarification"
    assert provider.structured_calls[0].output_schema.__name__ == (
        "ContradictionJudgeResultContext"
    )


def test_contradiction_review_free_form_question_without_structured_intent_is_not_pending() -> None:
    provider = ScriptedToolCallingProvider(
        [{"content": "This looks suspicious. Which city was correct?"}],
        structured_payloads=[
            {
                "judge_request_id": "judge-1",
                "intent": "emit_verdict",
                "decision": "nuance",
                "severity": "low",
                "reason": "The wording can be stored as nuance rather than a blocking conflict.",
                "graph_action": "allow_write",
            }
        ],
    )
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(
        _conversation("I met Marco in Milan."),
        AgenticToolExecutionContext(),
        start_state=AgenticStateId.CONTRADICTION_REVIEW,
    )

    assert result.status == "ok"
    assert result.metadata["contradiction_intent"] == "emit_verdict"


def test_structured_state_repairs_validation_error_once() -> None:
    provider = ScriptedToolCallingProvider(
        steps=[],
        structured_payloads=[
            {
                "summary": "Invalid slug ref shape.",
                "steps": [
                    {
                        "step_id": "node_step_0001",
                        "phase": "nodes",
                        "actions": [
                            {
                                "action_id": "node_action_0001",
                                "action_type": "create_node",
                                "target_refs": ["node_new_lorenzo"],
                            }
                        ],
                    }
                ],
                "node_plan_packet": {
                    "planned_refs": [
                        {
                            "ref": "node new lorenzo",
                            "object_kind": "node",
                            "label": "Person",
                            "name": "Lorenzo",
                        }
                    ],
                    "summary": "Invalid because the ref contains spaces.",
                },
            },
            {
                "summary": "Valid repaired slug ref.",
                "steps": [
                    {
                        "step_id": "node_step_0001",
                        "phase": "nodes",
                        "actions": [
                            {
                                "action_id": "node_action_0001",
                                "action_type": "create_node",
                                "target_refs": ["node_new_lorenzo"],
                            }
                        ],
                    }
                ],
                "node_plan_packet": {
                    "planned_refs": [
                        {
                            "ref": "node_new_lorenzo",
                            "object_kind": "node",
                            "label": "Person",
                            "name": "Lorenzo",
                        }
                    ],
                    "summary": "Repaired with a valid readable local ref.",
                },
            },
        ],
    )
    runner = AgenticStateRunner(provider=provider)
    result = runner.run_structured_state(
        AgenticStateInvocation(
            state_id=AgenticStateId.PLANNING_CHECKPOINT,
            context_payload=PlanningTransformContext(
                purpose=PlanningPurposeGuidelines(
                    purpose_id="memory_ingestion_nodes_planning",
                    goal="Plan nodes.",
                    output_usage="NodeMemoryPlan",
                ),
                expected_output_schema="NodeMemoryPlan",
                conversation=ConversationContext(
                    current_message=NeutralConversationMessage.user(
                        "Remember Lorenzo at the beach."
                    ),
                ),
            ),
            execution_context=AgenticToolExecutionContext(),
            metadata={"prompt_id_override": "memory_node_planning"},
        ),
        output_schema=NodeMemoryPlan,
    )

    assert result.status == "ok"
    assert result.structured_output is not None
    assert (
        result.structured_output["node_plan_packet"]["planned_refs"][0]["ref"] == "node_new_lorenzo"
    )
    assert provider.completion_calls == 2
    repair_messages = provider.completion_messages[-1]
    assert repair_messages[-1].role == "user"
    assert "Repair your previous response" in repair_messages[-1].content
    assert "node_new_lorenzo" in repair_messages[-1].content
