from __future__ import annotations

import pytest

from my_digital_brain.graph.exceptions import (
    GraphConflictError,
    GraphNotFoundError,
    GraphValidationError,
)
from my_digital_brain.graph.models import LifecycleTransitionRequest
from my_digital_brain.graph.service import GraphService


class FakeGraphRepository:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, object]] = {}
        self.relationships: list[dict[str, object]] = []

    def upsert_node(self, label: str, properties: dict[str, object]) -> dict[str, object]:
        node = {"label": label, "labels": [label], "properties": dict(properties)}
        self.nodes[str(properties["id"])] = node
        return node

    def patch_node(self, node_id: str, properties: dict[str, object]) -> dict[str, object] | None:
        node = self.nodes.get(node_id)
        if node is None:
            return None
        node_properties = dict(node["properties"])
        node_properties.update(properties)
        node["properties"] = node_properties
        return node

    def get_node(self, node_id: str) -> dict[str, object] | None:
        return self.nodes.get(node_id)

    def search_nodes(self, **_kwargs: object) -> list[dict[str, object]]:
        return list(self.nodes.values())

    def upsert_relationship(
        self,
        relationship_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, object],
    ) -> dict[str, object] | None:
        for relationship in self.relationships:
            if relationship["properties"]["id"] == properties["id"]:
                relationship["properties"] = dict(properties)
                return relationship
        relationship = {
            "type": relationship_type,
            "from_id": from_id,
            "to_id": to_id,
            "properties": dict(properties),
        }
        self.relationships.append(relationship)
        return relationship

    def get_relationship(self, relationship_id: str) -> dict[str, object] | None:
        for relationship in self.relationships:
            if relationship["properties"]["id"] == relationship_id:
                return relationship
        return None

    def patch_relationship(
        self,
        relationship_id: str,
        properties: dict[str, object],
    ) -> dict[str, object] | None:
        relationship = self.get_relationship(relationship_id)
        if relationship is None:
            return None
        relationship_properties = dict(relationship["properties"])
        relationship_properties.update(properties)
        relationship["properties"] = relationship_properties
        return relationship

    def get_node_relationships(
        self,
        node_id: str,
        relationship_type: str | None = None,
        direction: str = "both",
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        relationships = []
        for relationship in self.relationships:
            if relationship_type and relationship["type"] != relationship_type:
                continue
            outgoing = relationship["from_id"] == node_id
            incoming = relationship["to_id"] == node_id
            if direction == "out" and outgoing:
                relationships.append(relationship)
            elif direction == "in" and incoming:
                relationships.append(relationship)
            elif direction == "both" and (outgoing or incoming):
                relationships.append(relationship)
        return relationships

    def get_relationship_states(
        self,
        context_id: str,
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        state_ids = [
            relationship["to_id"]
            for relationship in self.relationships
            if relationship["type"] == "HAS_RELATIONSHIP_STATE"
            and relationship["from_id"] == context_id
        ]
        return [self.nodes[state_id] for state_id in state_ids]

    def clear_current_relationship_states(
        self,
        context_id: str,
        except_state_id: str,
        updated_at: str,
    ) -> list[dict[str, object]]:
        cleared = []
        for state in self.get_relationship_states(context_id):
            if state["properties"]["id"] == except_state_id:
                continue
            if state["properties"].get("is_current") is True:
                state["properties"]["is_current"] = False
                state["properties"]["updated_at"] = updated_at
                cleared.append(state)
        return cleared

    def find_change_records_for_target(
        self,
        target_id: str,
        target_kind: str | None = None,
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        records = []
        for node in self.nodes.values():
            if node["label"] != "ChangeRecord":
                continue
            properties = node["properties"]
            if properties.get("target_id") != target_id:
                continue
            if target_kind and properties.get("target_kind") != target_kind:
                continue
            records.append(node)
        return records

    def find_contradictions(
        self,
        target_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        contradiction_type: str | None = None,
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        linked_ids = None
        if target_id:
            linked_ids = {
                relationship["to_id"]
                for relationship in self.relationships
                if relationship["type"] == "HAS_CONTRADICTION_RECORD"
                and relationship["from_id"] == target_id
            }
        records = []
        for node in self.nodes.values():
            if node["label"] != "ContradictionRecord":
                continue
            if linked_ids is not None and node["properties"]["id"] not in linked_ids:
                continue
            properties = node["properties"]
            if status and properties.get("status") != status:
                continue
            if severity and properties.get("severity") != severity:
                continue
            if contradiction_type and properties.get("contradiction_type") != contradiction_type:
                continue
            records.append(node)
        return records

    def find_merges(
        self,
        canonical_node_id: str | None = None,
        merged_node_id: str | None = None,
        status: str | None = None,
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        records = []
        for node in self.nodes.values():
            if node["label"] != "MergeRecord":
                continue
            properties = node["properties"]
            if canonical_node_id and properties.get("canonical_node_id") != canonical_node_id:
                continue
            if merged_node_id and merged_node_id not in properties.get("merged_node_ids", []):
                continue
            if status and properties.get("status") != status:
                continue
            records.append(node)
        return records

    def get_neighborhood(self, *_args: object, **_kwargs: object) -> object:
        raise NotImplementedError

    def find_perceptions_for_target(
        self,
        *_args: object,
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        return []

    def find_relationship_contexts_for_target(
        self,
        *_args: object,
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        return []

    def find_affective_relationships(
        self,
        *_args: object,
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        return []


def test_upsert_node_validates_and_normalizes_name() -> None:
    service = GraphService(FakeGraphRepository())

    node = service.upsert_node(
        "Person",
        {"display_name": "  Marco   Rossi  ", "metadata": {"source": "test"}},
    )

    assert node.label == "Person"
    assert node.properties["display_name"] == "  Marco   Rossi  "
    assert node.properties["normalized_name"] == "marco rossi"
    assert node.properties["metadata"] == {"source": "test"}
    assert node.properties["created_at"]
    assert node.properties["updated_at"]


def test_upsert_node_rejects_unknown_properties() -> None:
    service = GraphService(FakeGraphRepository())

    with pytest.raises(GraphValidationError):
        service.upsert_node("Person", {"display_name": "Marco", "unsafe": True})


def test_patch_node_rejects_immutable_fields() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    node = service.upsert_node("Topic", {"name": "Graph memory"})

    with pytest.raises(GraphValidationError, match="id or created_at"):
        service.patch_node(node.properties["id"], {"id": "other-id"})


def test_patch_node_refreshes_normalized_name() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    node = service.upsert_node("Place", {"name": "Milan"})

    patched = service.patch_node(node.properties["id"], {"name": "New York"})

    assert patched.properties["normalized_name"] == "new york"


def test_upsert_relationship_rejects_unknown_type() -> None:
    service = GraphService(FakeGraphRepository())

    with pytest.raises(GraphValidationError, match="Unsupported graph relationship type"):
        service.upsert_relationship("UNSAFE", "from", "to", {})


def test_upsert_relationship_rejects_missing_endpoints() -> None:
    service = GraphService(FakeGraphRepository())

    with pytest.raises(GraphNotFoundError, match="source node"):
        service.upsert_relationship("RELATED_TO", "missing-from", "missing-to", {})


def test_upsert_relationship_accepts_affective_properties() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    source = service.upsert_node("Person", {"display_name": "Marco"})
    target = service.upsert_node("Place", {"name": "Milan"})

    relationship = service.upsert_relationship(
        "RELATED_TO",
        source.properties["id"],
        target.properties["id"],
        {
            "emotional_summary": "A place tied to friendship.",
            "emotional_valence": "positive",
            "source_ids": ["source-1"],
        },
    )

    assert relationship.type == "RELATED_TO"
    assert relationship.properties["emotional_summary"] == "A place tied to friendship."
    assert relationship.properties["source_ids"] == ["source-1"]


def test_create_relationship_state_updates_current_context_and_change_record() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    context = service.upsert_node(
        "RelationshipContext",
        {"description": "Old context", "status": "close"},
    )

    first_state = service.create_relationship_state(
        context.properties["id"],
        {
            "description": "We are now distant but calmer.",
            "status": "low_contact",
            "emotional_summary": "Mixed distance.",
            "resolved_start": "2024-01-01",
        },
    )
    second_state = service.create_relationship_state(
        context.properties["id"],
        {
            "description": "We reconnected.",
            "status": "reconnected",
            "resolved_start": "2025-01-01",
        },
    )

    patched_context = service.get_node(context.properties["id"])
    first_state_after = service.get_node(first_state.properties["id"])
    changes = service.get_change_records_for_target(
        context.properties["id"],
        target_kind="relationship_context",
    )

    assert second_state.label == "RelationshipState"
    assert first_state_after.properties["is_current"] is False
    assert patched_context.properties["status"] == "reconnected"
    assert changes[0].properties["field_path"] == "current_relationship_state"


def test_lifecycle_transition_creates_change_record() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    node = service.upsert_node("Topic", {"name": "Old project"})

    transitioned = service.transition_node_lifecycle(
        node.properties["id"],
        LifecycleTransitionRequest(lifecycle_state="archived", reason="No longer current"),
    )
    changes = service.get_change_records_for_target(node.properties["id"], target_kind="node")

    assert transitioned.properties["lifecycle_state"] == "archived"
    assert changes[0].properties["field_path"] == "lifecycle_state"
    assert changes[0].properties["previous_value_json"] == '"active"'
    assert changes[0].properties["new_value_json"] == '"archived"'


def test_relationship_lifecycle_transition_creates_relationship_change_record() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    source = service.upsert_node("Person", {"display_name": "Marco"})
    target = service.upsert_node("Place", {"name": "Milan"})
    relationship = service.upsert_relationship(
        "RELATED_TO",
        source.properties["id"],
        target.properties["id"],
        {},
    )

    transitioned = service.transition_relationship_lifecycle(
        relationship.properties["id"],
        LifecycleTransitionRequest(lifecycle_state="stale"),
    )
    changes = service.get_change_records_for_target(
        relationship.properties["id"],
        target_kind="relationship",
    )

    assert transitioned.properties["lifecycle_state"] == "stale"
    assert changes[0].properties["target_relationship_type"] == "RELATED_TO"


def test_contradiction_create_query_and_update() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    claim = service.upsert_node("Claim", {"text": "The event happened in Milan."})

    contradiction = service.create_contradiction(
        {
            "contradiction_type": "location",
            "severity": "medium",
            "reason": "Existing memory says Turin.",
        },
        target_ids=[claim.properties["id"]],
    )
    queried = service.query_contradictions(target_id=claim.properties["id"], status="detected")
    updated = service.update_contradiction(
        contradiction.properties["id"],
        {"status": "resolved", "resolution_summary": "User confirmed Milan."},
    )

    assert queried[0].properties["id"] == contradiction.properties["id"]
    assert updated.properties["status"] == "resolved"
    assert updated.properties["resolved_at"]


def test_merge_apply_archives_merged_node_without_rewiring_relationships() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    canonical = service.upsert_node(
        "Person",
        {"display_name": "Marco Rossi", "aliases": ["Marco"], "source_ids": ["source-1"]},
    )
    duplicate = service.upsert_node(
        "Person",
        {"display_name": "Marco from university", "aliases": ["Uni Marco"], "source_ids": ["s2"]},
    )
    place = service.upsert_node("Place", {"name": "Milan"})
    original_relationship = service.upsert_relationship(
        "RELATED_TO",
        duplicate.properties["id"],
        place.properties["id"],
        {},
    )
    merge = service.create_merge_record(
        canonical_node_id=canonical.properties["id"],
        merged_node_ids=[duplicate.properties["id"]],
        reason="Same university friend.",
    )

    applied = service.apply_merge(merge.properties["id"])
    archived_duplicate = service.get_node(duplicate.properties["id"])
    canonical_after = service.get_node(canonical.properties["id"])
    canonical_relationships = service.get_node_relationships(canonical.properties["id"])

    assert applied.properties["status"] == "applied"
    assert archived_duplicate.properties["lifecycle_state"] == "archived"
    assert archived_duplicate.properties["merged_into_id"] == canonical.properties["id"]
    assert canonical_after.properties["aliases"] == ["Marco", "Uni Marco"]
    assert canonical_after.properties["source_ids"] == ["source-1", "s2"]
    assert all(
        rel.properties["id"] != original_relationship.properties["id"]
        for rel in canonical_relationships
    )


def test_merge_validation_rejects_cross_label_self_and_repeated_apply() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    person = service.upsert_node("Person", {"display_name": "Marco"})
    other_person = service.upsert_node("Person", {"display_name": "Marco B."})
    place = service.upsert_node("Place", {"name": "Milan"})

    with pytest.raises(GraphValidationError, match="Canonical node cannot"):
        service.create_merge_record(
            canonical_node_id=person.properties["id"],
            merged_node_ids=[person.properties["id"]],
        )

    with pytest.raises(GraphValidationError, match="same primary label"):
        service.create_merge_record(
            canonical_node_id=person.properties["id"],
            merged_node_ids=[place.properties["id"]],
        )

    with pytest.raises(GraphValidationError, match="duplicate merged_node_ids"):
        service.create_merge_record(
            canonical_node_id=person.properties["id"],
            merged_node_ids=[other_person.properties["id"], other_person.properties["id"]],
        )

    merge = service.create_merge_record(
        canonical_node_id=person.properties["id"],
        merged_node_ids=[other_person.properties["id"]],
    )
    service.apply_merge(merge.properties["id"])
    with pytest.raises(GraphConflictError, match="already applied"):
        service.apply_merge(merge.properties["id"])


def test_canonical_resolution_detects_merge_cycles() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    first = service.upsert_node("Person", {"display_name": "A"})
    second = service.upsert_node("Person", {"display_name": "B"})
    service.upsert_relationship("MERGED_INTO", first.properties["id"], second.properties["id"], {})
    service.upsert_relationship("MERGED_INTO", second.properties["id"], first.properties["id"], {})

    with pytest.raises(GraphValidationError, match="Merge cycle"):
        service.get_canonical_node(first.properties["id"])
