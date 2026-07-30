from __future__ import annotations

import json

from my_digital_brain.agentic import (
    AgenticStateId,
    AgenticToolExecutionContext,
    build_agentic_tool_mapping,
    build_agentic_toolbox,
    default_agentic_tool_registry,
    default_state_configs,
)
from my_digital_brain.clarification.toolbox import ClarificationToolService
from my_digital_brain.graph.models import (
    EntityDetailResult,
    NodeSearchResult,
    RelationshipResult,
)
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry


class FakeClarificationGraph:
    def __init__(self) -> None:
        self.nodes = {
            "person:owner": _node("person:owner", "Owner"),
            "person:amos": _node("person:amos", "Amos Bianchi", aliases=["Amos"]),
        }

    def search_nodes(self, *, label=None, query=None, limit=25, **_kwargs):
        return [self.nodes["person:amos"]] if query else []

    def get_entity_detail(self, node_id: str, **_kwargs):
        return EntityDetailResult(
            target=self.nodes[node_id],
            relationships=[
                RelationshipResult(
                    type="KNOWS",
                    from_id=node_id,
                    to_id="person:owner",
                    properties={"id": "rel:amos:owner", "since": "2020"},
                )
            ],
        )

    def get_node_relationships(self, node_id: str, **_kwargs):
        return self.get_entity_detail(node_id).relationships


def _node(node_id: str, display_name: str, *, aliases: list[str] | None = None):
    return NodeSearchResult(
        label="Person",
        labels=["Person"],
        properties={"id": node_id, "display_name": display_name, "aliases": aliases or []},
    )


def _service() -> tuple[ClarificationToolService, RunReferenceRegistry]:
    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    registry.register_owner("person:owner", display_label="Owner")
    registry.register_proposal(
        "CANDIDATE_PERSON_001",
        label="Person",
        display_label="Amos",
    )
    return ClarificationToolService(FakeClarificationGraph(), registry), registry


def test_clarification_agent_exposes_only_wave2_tools() -> None:
    configs = default_state_configs()
    registry = default_agentic_tool_registry()
    state = configs[AgenticStateId.CLARIFICATION_AGENT]
    names = [definition.name for definition in registry.definitions_for_state(state)]
    assert names == [
        "lookup_candidates",
        "get_candidate_context",
        "get_relationship_context",
        "pick_one",
        "pick_many",
        "confirm",
        "ask_text",
        "ask_text_or_audio",
    ]
    assert set(state.forbidden_tools) >= {
        "ask_clarification",
        "create_graph_node",
        "patch_graph_node",
        "upsert_graph_relationship",
        "raw_graph_query",
    }


def test_lookup_registers_existing_model_ref_and_redacts_graph_id() -> None:
    service, registry = _service()
    result = service.lookup_candidates(
        candidate_ref="CANDIDATE_PERSON_001",
        entity_type="Person",
        display_name="Amos",
    )
    assert result.status == "ok"
    payload = json.dumps(result.model_dump(mode="json"))
    assert "person:amos" not in payload
    candidate = result.data["result"]["candidates"][0]
    assert candidate["ref"].startswith("NODE_")
    assert registry.resolve(candidate["ref"]) == "person:amos"


def test_context_and_relationship_tools_accept_refs_only() -> None:
    service, registry = _service()
    node_ref = registry.register_existing(
        "person:amos",
        object_kind="node",
        label="Person",
        display_label="Amos Bianchi",
    )
    context = service.get_candidate_context(refs=[node_ref])
    assert context.status == "ok"
    assert "person:amos" not in json.dumps(context.model_dump(mode="json"))
    relationship = service.get_relationship_context(
        from_ref=node_ref,
        to_ref="OWNER",
    )
    assert relationship.status == "ok"
    assert relationship.data["relationships"][0]["from_ref"] == node_ref
    assert relationship.data["relationships"][0]["to_ref"] == "OWNER"

    invalid = service.get_candidate_context(refs=["person:amos"])
    assert invalid.status == "error"
    assert invalid.error.code == "invalid_context_request"


def test_question_tools_enforce_semantic_modes_and_custom_answers() -> None:
    service, registry = _service()
    registry.register_existing(
        "person:amos",
        object_kind="node",
        label="Person",
        display_label="Amos Bianchi",
    )
    result = service.build_question(
        tool_name="pick_one",
        request={
            "question": "Which Amos is this?",
            "kind": "identity_ambiguous",
            "reason": "Several identities may match.",
            "target_refs": ["CANDIDATE_PERSON_001"],
            "evidence_refs": [],
            "options": [
                {
                    "label": "Amos Bianchi",
                    "summary": "Existing person",
                    "target_ref": "NODE_000001",
                },
            ],
            "allow_custom_answer": True,
        },
        frame_id="frame-1",
        tool_call_id="call-1",
        origin_state_id="clarification_agent",
    )
    assert result.status == "pending"
    packet = result.data["clarification_packet"]
    assert packet["questions"][0]["response_mode"] == "single_choice"
    assert packet["questions"][0]["options"][0]["option_id"]

    invalid = service.build_question(
        tool_name="confirm",
        request={
            "question": "Confirm?",
            "kind": "confirm_proposal",
            "reason": "Need confirmation.",
            "target_refs": [],
            "evidence_refs": [],
            "options": [
                {
                    "label": "Yes",
                    "summary": None,
                    "target_ref": None,
                    "recommended": False,
                }
            ],
            "allow_custom_answer": True,
        },
        frame_id="frame-1",
        tool_call_id="call-2",
        origin_state_id="clarification_agent",
    )
    assert invalid.status == "error"


def test_agentic_factory_builds_strict_wave2_schemas() -> None:
    state = default_state_configs()[AgenticStateId.CLARIFICATION_AGENT]
    toolbox = build_agentic_toolbox(state)
    mapping = build_agentic_tool_mapping(
        state,
        AgenticToolExecutionContext(
            frame_id="frame-1",
            session_id="session-1",
            current_payload={
                "reference_registry_snapshot": _service()[1].snapshot(),
            },
        ),
    )
    assert set(toolbox.tools_by_name) == set(mapping)
    assert "at most five" in toolbox.tools_by_name["pick_one"]["function"]["description"]
    assert toolbox.tools_by_name["lookup_candidates"]["function"]["strict"] is True
