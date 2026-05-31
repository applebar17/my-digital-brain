from __future__ import annotations

import os
from pathlib import Path

import pytest

from my_digital_brain.config import get_settings
from my_digital_brain.core.ids import new_uuid
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


def test_graph_wave2_memory_semantics_round_trip() -> None:
    pytest.importorskip("neo4j")
    settings = get_settings()
    with GraphClient.from_settings(settings) as client:
        runner = Neo4jMigrationRunner(client, Path("migrations/graph"))
        runner.run()
        assert runner.run() == []
        service = GraphService(GraphRepository(client))

        context = service.upsert_node(
            "RelationshipContext",
            {
                "id": new_uuid(),
                "description": "Old relationship summary.",
                "status": "close",
            },
        )
        state = service.create_relationship_state(
            context.properties["id"],
            {
                "id": new_uuid(),
                "description": "We are distant now.",
                "status": "low_contact",
                "resolved_start": "2024-01-01",
            },
        )
        refreshed_context = service.get_node(context.properties["id"])
        changes = service.get_change_records_for_target(
            context.properties["id"],
            target_kind="relationship_context",
        )

        assert state.label == "RelationshipState"
        assert refreshed_context.properties["status"] == "low_contact"
        assert changes

        contradiction = service.create_contradiction(
            {
                "id": new_uuid(),
                "contradiction_type": "relationship",
                "severity": "low",
            },
            target_ids=[context.properties["id"]],
        )
        contradictions = service.query_contradictions(target_id=context.properties["id"])

        assert contradictions[0].properties["id"] == contradiction.properties["id"]

        canonical = service.upsert_node(
            "Person",
            {"id": new_uuid(), "display_name": "Marco", "aliases": ["Marco"]},
        )
        duplicate = service.upsert_node(
            "Person",
            {"id": new_uuid(), "display_name": "Marco from university", "aliases": ["Uni Marco"]},
        )
        merge = service.create_merge_record(
            canonical_node_id=canonical.properties["id"],
            merged_node_ids=[duplicate.properties["id"]],
            reason="Integration-test duplicate.",
        )
        applied = service.apply_merge(merge.properties["id"])
        archived_duplicate = service.get_node(duplicate.properties["id"])
        canonical_after = service.get_canonical_node(duplicate.properties["id"])

        assert applied.properties["status"] == "applied"
        assert archived_duplicate.properties["lifecycle_state"] == "archived"
        assert canonical_after.properties["id"] == canonical.properties["id"]


def test_graph_wave3_query_foundation_round_trip() -> None:
    pytest.importorskip("neo4j")
    settings = get_settings()
    with GraphClient.from_settings(settings) as client:
        runner = Neo4jMigrationRunner(client, Path("migrations/graph"))
        runner.run()
        assert runner.run() == []
        service = GraphService(GraphRepository(client))

        person = service.upsert_node("Person", {"id": new_uuid(), "display_name": "Me"})
        animal = service.upsert_node(
            "Animal",
            {"id": new_uuid(), "name": "Luna", "species": "dog"},
        )
        circle = service.upsert_node(
            "SocialCircle",
            {"id": new_uuid(), "name": "Family", "circle_type": "family"},
        )
        place = service.upsert_node(
            "Place",
            {
                "id": new_uuid(),
                "name": "Athens",
                "city": "Athens",
                "country": "Greece",
                "latitude": 37.9838,
                "longitude": 23.7275,
            },
        )
        event = service.upsert_node(
            "Event",
            {
                "id": new_uuid(),
                "title": "Greek vacation",
                "resolved_start": "2024-08-01",
            },
        )
        service.upsert_relationship("LIVES_WITH", animal.properties["id"], person.properties["id"], {})
        service.upsert_relationship("MEMBER_OF", person.properties["id"], circle.properties["id"], {})
        service.upsert_relationship("HAPPENED_AT", event.properties["id"], place.properties["id"], {})
        service.upsert_relationship("PARTICIPATED_IN", person.properties["id"], event.properties["id"], {})

        timeline = service.get_timeline_for_node(person.properties["id"])
        map_view = service.get_map_view(city="Athens", country="Greece")
        context_package = service.get_context_package(person.properties["id"])

        assert animal.properties["normalized_name"] == "luna"
        assert circle.properties["normalized_name"] == "family"
        assert timeline.items[0].title == "Greek vacation"
        assert map_view.places[0].title == "Athens"
        assert context_package.target["alias"] == "NODE_000001"
