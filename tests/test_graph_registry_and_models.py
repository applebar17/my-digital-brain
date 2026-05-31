from __future__ import annotations

import json
from pathlib import Path

import pytest

from my_digital_brain.graph.exceptions import GraphValidationError
from my_digital_brain.graph.models import (
    AnimalNode,
    ChangeRecordNode,
    ContradictionRecordNode,
    GraphContextPackage,
    GraphRelationshipModel,
    GraphViewNode,
    MergeRecordNode,
    PerceptionNode,
    PersonNode,
    RelationshipStateNode,
    SocialCircleNode,
    TimelineItem,
)
from my_digital_brain.graph.registry import (
    CORE_NODE_LABELS,
    CORE_RELATIONSHIP_TYPES,
    validate_node_label,
    validate_relationship_type,
)
from my_digital_brain.graph.serialization import from_neo4j_properties, to_neo4j_properties


def test_node_registry_accepts_core_labels() -> None:
    for label in CORE_NODE_LABELS:
        assert validate_node_label(label) == label


def test_node_registry_rejects_unknown_label() -> None:
    with pytest.raises(GraphValidationError, match="Unsupported graph node label"):
        validate_node_label("UnsafeLabel")


def test_relationship_registry_accepts_core_types() -> None:
    for relationship_type in CORE_RELATIONSHIP_TYPES:
        assert validate_relationship_type(relationship_type) == relationship_type


def test_relationship_registry_rejects_unknown_type() -> None:
    with pytest.raises(GraphValidationError, match="Unsupported graph relationship type"):
        validate_relationship_type("DROP_ALL")


def test_core_node_model_accepts_metadata_provenance_and_affective_fields() -> None:
    node = PersonNode(
        display_name="Alessandro",
        metadata={"source": "fixture", "rank": 1},
        source_ids=["source-1"],
        extraction_run_ids=["run-1"],
        emotional_summary="Warm past bond mixed with distance.",
        emotional_valence="mixed",
        emotional_intensity=0.6,
        emotion_tags=["warmth", "distance"],
        original_user_words="Great relationship during teenage years.",
    )

    dumped = node.model_dump(mode="json")

    assert dumped["display_name"] == "Alessandro"
    assert dumped["privacy_level"] == "normal"
    assert dumped["lifecycle_state"] == "active"
    assert dumped["metadata"]["source"] == "fixture"
    assert dumped["source_ids"] == ["source-1"]
    assert dumped["emotion_tags"] == ["warmth", "distance"]
    assert "resolved_start" in dumped


def test_perception_can_target_non_person_memory() -> None:
    perception = PerceptionNode(
        target_type="Place",
        description="The user remembers the place as comforting.",
        emotional_valence="positive",
        source_kind="user_stated",
    )

    assert perception.target_type == "Place"
    assert perception.emotional_valence == "positive"


def test_relationship_model_accepts_affective_and_provenance_fields() -> None:
    relationship = GraphRelationshipModel(
        source_ids=["source-1"],
        extraction_run_ids=["run-1"],
        emotional_summary="Stressful but meaningful collaboration.",
        emotional_valence="mixed",
        emotion_tags=["stress", "meaning"],
    )

    assert relationship.emotional_summary == "Stressful but meaningful collaboration."
    assert relationship.source_ids == ["source-1"]


def test_wave2_models_accept_temporal_history_and_audit_fields() -> None:
    state = RelationshipStateNode(
        status="low_contact",
        description="We stopped talking regularly.",
        resolved_start="2020-01-01",
        time_basis="user_stated",
        timezone="Europe/Rome",
        is_current=True,
    )
    change = ChangeRecordNode(
        target_kind="node",
        target_id="node-1",
        target_label="Person",
        field_path="lifecycle_state",
        previous_value_json='"active"',
        new_value_json='"archived"',
    )
    contradiction = ContradictionRecordNode(
        contradiction_type="location",
        severity="medium",
        reason="Conflicting event location.",
    )
    merge = MergeRecordNode(
        canonical_node_id="node-1",
        merged_node_ids=["node-2"],
        reason="Same person.",
    )

    assert state.resolved_start == "2020-01-01"
    assert change.field_path == "lifecycle_state"
    assert contradiction.status == "detected"
    assert merge.status == "proposed"


def test_wave3_models_accept_animals_social_circles_and_read_views() -> None:
    animal = AnimalNode(
        name="Luna",
        species="dog",
        emotional_summary="A comforting presence at home.",
    )
    circle = SocialCircleNode(name="Close friends", circle_type="friendship")
    timeline_item = TimelineItem(
        id="event-1",
        label="Event",
        title="Greek vacation",
        time_value="2024-08-01",
        emotional_summary="A memory tied to freedom.",
    )
    view_node = GraphViewNode(
        id="place-1",
        label="Place",
        title="Athens",
        latitude=37.9838,
        longitude=23.7275,
        display_metadata={"country": "Greece"},
    )
    context_package = GraphContextPackage(
        target={"alias": "NODE_000001", "label": "Animal", "title": "Luna"},
        current_facts=[{"field": "species", "value": "dog"}],
        alias_map={"NODE_000001": animal.id},
    )

    assert animal.species == "dog"
    assert circle.circle_type == "friendship"
    assert timeline_item.time_value == "2024-08-01"
    assert view_node.display_metadata["country"] == "Greece"
    assert context_package.target["title"] == "Luna"


def test_metadata_serializes_as_deterministic_json_and_round_trips() -> None:
    properties = to_neo4j_properties(
        {
            "id": "node-1",
            "metadata": {"z": 1, "a": {"nested": True}},
            "emotion_tags": ["warmth"],
        },
        exclude_none=True,
    )

    assert properties["metadata_json"] == json.dumps(
        {"a": {"nested": True}, "z": 1},
        sort_keys=True,
        separators=(",", ":"),
    )

    decoded = from_neo4j_properties(properties)

    assert decoded["metadata"] == {"a": {"nested": True}, "z": 1}
    assert decoded["emotion_tags"] == ["warmth"]


def test_sample_affective_memory_fixture_uses_core_graph_contract() -> None:
    fixture_path = Path("tests/fixtures/sample_affective_memory.json")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    for node in fixture["nodes"]:
        assert validate_node_label(node["label"]) == node["label"]
    for relationship in fixture["relationships"]:
        assert validate_relationship_type(relationship["type"]) == relationship["type"]

    perception_targets = [
        node["properties"].get("target_type")
        for node in fixture["nodes"]
        if node["label"] == "Perception"
    ]
    assert "Person" in perception_targets
