from __future__ import annotations

import json

from my_digital_brain.agentic.enums import RefObjectKind
from my_digital_brain.agentic.refs import RefContext
from my_digital_brain.agentic.state import default_state_configs
from my_digital_brain.agentic.tools import AgenticToolExecutionContext, build_agentic_tool_mapping
from my_digital_brain.agentic.runtime import AgenticRuntime, _replace_pending_tool_messages
from my_digital_brain.chat.models import AgenticFrame
from my_digital_brain.chat.store import InMemoryChatSessionStore
from my_digital_brain.clarification.contracts import ClarificationPacket, ClarificationQuestion
from my_digital_brain.graph.models import NodeSearchResult
from my_digital_brain.agentic.tools.bindings import _graph_context_from_retrieval
from my_digital_brain.clarification.toolbox import ClarificationToolService


def test_retrieval_context_maps_graph_ids_to_one_model_reference_context() -> None:
    retrieval = {
        "status": "ok",
        "result": {
            "context_packages": [
                {
                    "package_id": "package-1",
                    "target": {
                        "id": "person-lorenzo",
                        "label": "Person",
                        "display_name": "Lorenzo",
                    },
                    "relationships": [
                        {
                            "id": "relationship-1",
                            "from_id": "person-lorenzo",
                            "to_id": "person-marco",
                            "type": "KNOWS",
                        },
                    ],
                },
            ],
            "hits": [],
        },
    }
    refs = RefContext(session_id="session-1")
    graph_context = _graph_context_from_retrieval(retrieval, ref_context=refs)

    assert graph_context is not None
    lorenzo_ref = refs.ref_for_backend_id("person-lorenzo")
    relationship_ref = refs.ref_for_backend_id("relationship-1")
    assert lorenzo_ref == "node_0001"
    assert relationship_ref == "edge_0001"
    rendered = graph_context.model_facing_payload()
    rendered_json = json.dumps(rendered)
    assert "person-lorenzo" not in rendered_json
    assert "relationship-1" not in rendered_json
    assert lorenzo_ref in rendered_json
    assert "ref_context" in rendered


def test_clarification_question_uses_canonical_refs_and_allows_proposals() -> None:
    refs = RefContext(session_id="session-1")
    refs.register_proposed(
        "node_new_lorenzo",
        RefObjectKind.NODE,
        label="Person",
        name="Lorenzo",
    )
    result = ClarificationToolService(graph_service=None, ref_context=refs).build_question(
        tool_name="confirm",
        request={
            "question": "Is this the Lorenzo you mentioned?",
            "kind": "confirm_proposal",
            "reason": "The new person has not been bound to a graph identity yet.",
            "target_refs": ["node_new_lorenzo"],
            "options": [
                {"label": "Yes", "summary": "Keep this proposed person."},
                {"label": "No", "summary": "Do not keep this proposed person."},
            ],
        },
        frame_id="frame-1",
        tool_call_id="call-1",
        origin_state_id="clarification_agent",
    )

    assert result.status == "pending"
    packet = result.data["clarification_packet"]
    assert packet["target_refs"] == ["node_new_lorenzo"]
    assert "node_new_lorenzo" in packet["questions"][0]["target_refs"]


def test_graph_write_resolves_model_ref_only_at_backend_boundary() -> None:
    class Graph:
        def __init__(self) -> None:
            self.received_node_id: str | None = None

        def patch_node(self, node_id: str, _properties: dict) -> NodeSearchResult:
            self.received_node_id = node_id
            return NodeSearchResult(
                label="Person",
                labels=["Person"],
                properties={"id": node_id, "display_name": "Lorenzo"},
            )

        def get_node(self, node_id: str) -> NodeSearchResult:
            return NodeSearchResult(
                label="Person",
                labels=["Person"],
                properties={"id": node_id, "display_name": "Lorenzo"},
            )

    refs = RefContext(session_id="session-1")
    refs.register_existing(
        "person-lorenzo",
        RefObjectKind.NODE,
        label="Person",
        name="Lorenzo",
    )
    graph = Graph()
    context = AgenticToolExecutionContext(graph_service=graph, ref_context=refs)
    mapping = build_agentic_tool_mapping(
        default_state_configs()["graph_update"],
        context,
    )

    result = mapping["patch_person_node"](
        node_id="node_0001",
        person={
            "description": "Known as Lory.",
            "display_name": None,
            "aliases": None,
            "known_since": None,
            "status": None,
        },
    )

    assert result.status == "ok"
    assert graph.received_node_id == "person-lorenzo"
    assert result.data["updated_refs"] == ["node_0001"]


def test_request_owner_binding_replaces_stale_frame_owner_mapping() -> None:
    refs = RefContext(session_id="session-1")
    refs.bind_owner("owner-local", name="Old owner")
    context = AgenticToolExecutionContext(
        graph_owner_id="person:owner",
        ref_context=refs,
    )

    AgenticRuntime._bind_request_owner(context, None)

    assert refs.resolve("OWNER", expected_kind=RefObjectKind.NODE) == "person:owner"
    assert "owner-local" not in json.dumps(refs.model_facing_packet())
    assert "person:owner" not in json.dumps(refs.model_facing_packet())


def test_nested_interruption_returns_the_packet_persisted_on_child_frame() -> None:
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel="web",
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    packet = ClarificationPacket(
        frame_id="child-frame",
        tool_call_id="ask-text-call",
        tool_name="ask_text",
        origin_state_id="clarification_agent",
        reason="Need one detail.",
        questions=[
            ClarificationQuestion(
                question="Who is Lorenzo?",
                kind="identity_no_match",
                response_mode="free_text",
            ),
        ],
    )
    store.save_agentic_frame(
        session.session_id,
        AgenticFrame(
            frame_id="child-frame",
            session_id=session.session_id,
            state_id="clarification_agent",
            status="interrupted",
            active_tool_call_id="ask-text-call",
            active_tool_name="ask_text",
            clarification_packet=packet,
        ),
    )
    context = AgenticToolExecutionContext(
        chat_store=store,
        session_id=session.session_id,
    )

    result = AgenticRuntime.__new__(AgenticRuntime)._canonicalize_child_interruption(
        context,
        {
            "frame_id": "child-frame",
            "tool_call_id": "outer-call",
            "clarification_packet": {"packet_id": "outer-packet"},
        },
    )

    assert result["tool_call_id"] == "ask-text-call"
    assert result["clarification_packet"]["packet_id"] == packet.packet_id


def test_resume_replaces_pending_tool_result_instead_of_appending_orphan() -> None:
    from my_digital_brain.ai.models import ToolResult

    messages = [
        {"role": "user", "content": "Need clarification."},
        {
            "role": "assistant",
            "tool_calls": [{"id": "ask-text-call", "type": "function"}],
        },
        {
            "role": "tool",
            "tool_call_id": "ask-text-call",
            "content": '{"status":"pending"}',
        },
    ]

    resumed = _replace_pending_tool_messages(
        messages,
        ["ask-text-call"],
        ToolResult(status="ok", output="Lorenzo is my brother."),
    )

    assert len(resumed) == len(messages)
    assert resumed[-1]["tool_call_id"] == "ask-text-call"
    assert '"status":"ok"' in resumed[-1]["content"]
