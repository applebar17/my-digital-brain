from __future__ import annotations

import pytest

from my_digital_brain.graph.exceptions import GraphNotFoundError, GraphValidationError
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
        relationship = {
            "type": relationship_type,
            "from_id": from_id,
            "to_id": to_id,
            "properties": dict(properties),
        }
        self.relationships.append(relationship)
        return relationship

    def get_node_relationships(self, *_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return self.relationships

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
