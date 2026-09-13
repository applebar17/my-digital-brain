from __future__ import annotations

import json

from my_digital_brain.agentic.enums import RefObjectKind
from my_digital_brain.agentic.refs import RefContext
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
