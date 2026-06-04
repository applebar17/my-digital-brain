from __future__ import annotations

from typing import Any

import pytest

from my_digital_brain.graph.exceptions import GraphValidationError
from my_digital_brain.graph.repository_core import GraphCoreRepository
from my_digital_brain.graph.repository_records import relationship_from_record


class FakeGraphClient:
    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self.records = records or []
        self.read_calls: list[tuple[str, dict[str, Any]]] = []

    def execute_read(self, cypher: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        self.read_calls.append((cypher, parameters))
        return self.records


def test_search_nodes_uses_broad_memory_search_fields() -> None:
    client = FakeGraphClient(
        [
            {
                "labels": ["Perception"],
                "properties": {
                    "id": "perception-1",
                    "emotional_summary": "Oppressive personality traits.",
                },
            }
        ]
    )
    repository = GraphCoreRepository(client)

    results = repository.search_nodes(query="Oppressive")

    assert results[0]["label"] == "Perception"
    assert results[0]["properties"]["id"] == "perception-1"
    cypher, parameters = client.read_calls[0]
    assert parameters["query"] == "oppressive"
    assert "description" in parameters["text_search_fields"]
    assert "emotional_summary" in parameters["text_search_fields"]
    assert "original_user_words" in parameters["text_search_fields"]
    assert "relationship_type" in parameters["text_search_fields"]
    assert "aliases" in parameters["list_search_fields"]
    assert "emotion_tags" in parameters["list_search_fields"]
    assert "props[field]" in cypher


def test_search_nodes_rejects_unknown_label_before_cypher_execution() -> None:
    client = FakeGraphClient()
    repository = GraphCoreRepository(client)

    with pytest.raises(GraphValidationError):
        repository.search_nodes(label="Unsafe")

    assert client.read_calls == []


def test_relationship_from_record_accepts_neo4j_style_relationship_type_alias() -> None:
    relationship = relationship_from_record(
        {
            "_type": "RELATED_TO",
            "start_id": "node-1",
            "end_id": "node-2",
            "properties": {"description": "Related memory"},
        }
    )

    assert relationship == {
        "type": "RELATED_TO",
        "from_id": "node-1",
        "to_id": "node-2",
        "properties": {
            "id": "node-1:RELATED_TO:node-2",
            "description": "Related memory",
            "metadata": {},
        },
    }
