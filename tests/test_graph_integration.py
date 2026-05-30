from __future__ import annotations

import os
from pathlib import Path

import pytest

from my_digital_brain.config import get_settings
from my_digital_brain.graph.repository import GraphRepository
from my_digital_brain.graph.service import GraphService
from my_digital_brain.migrations.graph import Neo4jMigrationRunner
from my_digital_brain.storage.graph import GraphClient


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_NEO4J_INTEGRATION") != "1",
    reason="Set RUN_NEO4J_INTEGRATION=1 to run Neo4j integration tests.",
)


def test_graph_wave1_affective_memory_round_trip() -> None:
    pytest.importorskip("neo4j")
    settings = get_settings()
    with GraphClient.from_settings(settings) as client:
        runner = Neo4jMigrationRunner(client, Path("migrations/graph"))
        runner.run()
        service = GraphService(GraphRepository(client))

        place = service.upsert_node(
            "Place",
            {
                "id": "10000000-0000-4000-8000-000000000001",
                "name": "Milan",
                "emotional_summary": "A place remembered as energizing.",
                "emotional_valence": "positive",
            },
        )
        perception = service.upsert_node(
            "Perception",
            {
                "id": "10000000-0000-4000-8000-000000000002",
                "target_type": "Place",
                "description": "The user remembers the place as energizing.",
                "source_kind": "user_stated",
            },
        )
        service.upsert_relationship(
            "PERCEPTION_OF",
            perception.properties["id"],
            place.properties["id"],
            {"id": "10000000-0000-4000-8000-000000000003"},
        )

        context = service.get_affective_context(place.properties["id"])

        assert context.direct_affective_fields["emotional_summary"] == (
            "A place remembered as energizing."
        )
        assert context.perceptions[0].properties["target_type"] == "Place"
