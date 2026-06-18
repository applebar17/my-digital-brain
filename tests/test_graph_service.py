from __future__ import annotations

import pytest

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.graph.exceptions import (
    GraphConflictError,
    GraphNotFoundError,
    GraphValidationError,
)
from my_digital_brain.graph.models import LifecycleTransitionRequest, NeighborhoodResult
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

    def find_memory_logs_for_target(
        self,
        target_id: str,
        from_time: str | None = None,
        to_time: str | None = None,
        log_kind: str | None = None,
        source_kind: str | None = None,
        involved_target_id: str | None = None,
        media_only: bool = False,
        include_archived: bool = False,
        limit: int = 50,
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        log_ids = {
            relationship["to_id"]
            for relationship in self.relationships
            if relationship["type"] == "HAS_MEMORY_LOG"
            and relationship["from_id"] == target_id
        }
        logs = [
            node
            for node in self.nodes.values()
            if node["label"] == "MemoryLog" and node["properties"]["id"] in log_ids
        ]
        if not include_archived:
            logs = [
                node
                for node in logs
                if node["properties"].get("lifecycle_state", "active") != "archived"
            ]
        if log_kind:
            logs = [node for node in logs if node["properties"].get("log_kind") == log_kind]
        if source_kind:
            logs = [node for node in logs if node["properties"].get("source_kind") == source_kind]
        if from_time:
            logs = [node for node in logs if _memory_log_time(node) >= from_time]
        if to_time:
            logs = [node for node in logs if _memory_log_time(node) <= to_time]
        if involved_target_id:
            logs = [
                node
                for node in logs
                if involved_target_id in node["properties"].get("involved_target_ids", [])
                or any(
                    relationship["type"] == "INVOLVES"
                    and relationship["from_id"] == node["properties"]["id"]
                    and relationship["to_id"] == involved_target_id
                    for relationship in self.relationships
                )
            ]
        if media_only:
            logs = [
                node
                for node in logs
                if node["properties"].get("media_refs")
                or any(
                    relationship["type"] == "HAS_MEDIA"
                    and relationship["from_id"] == node["properties"]["id"]
                    for relationship in self.relationships
                )
            ]
        return sorted(logs, key=_memory_log_time, reverse=True)[:limit]

    def get_memory_log_detail(
        self,
        log_id: str,
        **_kwargs: object,
    ) -> dict[str, object] | None:
        log = self.nodes.get(log_id)
        if log is None or log["label"] != "MemoryLog":
            return None
        relationships = [
            relationship
            for relationship in self.relationships
            if relationship["from_id"] == log_id or relationship["to_id"] == log_id
        ]
        target_ids = {
            relationship["to_id"]
            if relationship["from_id"] == log_id
            else relationship["from_id"]
            for relationship in relationships
        }
        return {
            "memory_log": log,
            "relationships": relationships,
            "targets": [self.nodes[str(target_id)] for target_id in target_ids],
        }

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

    def get_neighborhood(
        self,
        node_id: str,
        depth: int = 1,
        **_kwargs: object,
    ) -> NeighborhoodResult:
        seen_node_ids = {node_id}
        frontier = {node_id}
        included_relationships: list[dict[str, object]] = []
        for _ in range(depth):
            next_frontier: set[str] = set()
            for relationship in self.relationships:
                from_id = str(relationship["from_id"])
                to_id = str(relationship["to_id"])
                if from_id not in frontier and to_id not in frontier:
                    continue
                if relationship not in included_relationships:
                    included_relationships.append(relationship)
                for linked_id in (from_id, to_id):
                    if linked_id not in seen_node_ids:
                        seen_node_ids.add(linked_id)
                        next_frontier.add(linked_id)
            frontier = next_frontier
        return NeighborhoodResult(
            nodes=[self.nodes[node_id] for node_id in seen_node_ids if node_id in self.nodes],
            relationships=included_relationships,
        )

    def get_related_records(self, node_id: str, **kwargs: object) -> NeighborhoodResult:
        return self.get_neighborhood(node_id, **kwargs)

    def find_sources_for_target(
        self,
        target_id: str,
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        source_ids = {
            relationship["from_id"]
            if self.nodes[str(relationship["from_id"])]["label"] == "Source"
            else relationship["to_id"]
            for relationship in self.relationships
            if relationship["type"] in {"MENTIONED_IN", "SUPPORTED_BY", "DERIVED_FROM"}
            and (relationship["from_id"] == target_id or relationship["to_id"] == target_id)
            and (
                self.nodes.get(str(relationship["from_id"]), {}).get("label") == "Source"
                or self.nodes.get(str(relationship["to_id"]), {}).get("label") == "Source"
            )
        }
        return [self.nodes[str(source_id)] for source_id in source_ids]

    def find_map_records(
        self,
        city: str | None = None,
        country: str | None = None,
        **_kwargs: object,
    ) -> NeighborhoodResult:
        city = city.lower().strip() if city else None
        country = country.lower().strip() if country else None
        place_ids = {
            str(node["properties"]["id"])
            for node in self.nodes.values()
            if node["label"] == "Place"
            and (city is None or str(node["properties"].get("city", "")).lower() == city)
            and (country is None or str(node["properties"].get("country", "")).lower() == country)
            and (
                node["properties"].get("latitude") is not None
                or node["properties"].get("longitude") is not None
                or city is not None
                or country is not None
            )
        }
        relationships = [
            relationship
            for relationship in self.relationships
            if relationship["type"] == "HAPPENED_AT" and relationship["to_id"] in place_ids
        ]
        node_ids = set(place_ids)
        node_ids.update(str(relationship["from_id"]) for relationship in relationships)
        return NeighborhoodResult(
            nodes=[self.nodes[node_id] for node_id in node_ids if node_id in self.nodes],
            relationships=relationships,
        )

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

    def count_nodes_by_label(self, include_archived: bool = False) -> dict[str, int]:
        counts: dict[str, int] = {}
        for node in self.nodes.values():
            if (
                not include_archived
                and node["properties"].get("lifecycle_state") == "archived"
            ):
                continue
            label = str(node["label"])
            counts[label] = counts.get(label, 0) + 1
        return counts

    def count_relationships_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for relationship in self.relationships:
            relationship_type = str(relationship["type"])
            counts[relationship_type] = counts.get(relationship_type, 0) + 1
        return counts

    def top_connected_nodes(
        self,
        include_archived: bool = False,
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        items = []
        for node_id, node in self.nodes.items():
            if (
                not include_archived
                and node["properties"].get("lifecycle_state") == "archived"
            ):
                continue
            count = sum(
                1
                for relationship in self.relationships
                if relationship["from_id"] == node_id or relationship["to_id"] == node_id
            )
            if count:
                items.append({"node": node, "count": count})
        return sorted(items, key=lambda item: item["count"], reverse=True)

    def top_emotion_tags(
        self,
        include_archived: bool = False,
        **_kwargs: object,
    ) -> list[dict[str, object]]:
        counts: dict[str, int] = {}
        for node in self.nodes.values():
            if (
                not include_archived
                and node["properties"].get("lifecycle_state") == "archived"
            ):
                continue
            for tag in node["properties"].get("emotion_tags", []):
                counts[str(tag)] = counts.get(str(tag), 0) + 1
        return [{"tag": tag, "count": count} for tag, count in counts.items()]

    def count_unresolved_contradictions(self) -> int:
        return sum(
            1
            for node in self.nodes.values()
            if node["label"] == "ContradictionRecord"
            and node["properties"].get("status", "detected")
            in {"detected", "needs_clarification"}
        )


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


def test_wave3_animal_and_social_circle_names_are_normalized() -> None:
    service = GraphService(FakeGraphRepository())

    animal = service.upsert_node("Animal", {"name": "  Luna  "})
    circle = service.upsert_node("SocialCircle", {"name": " Close Friends "})

    assert animal.properties["normalized_name"] == "luna"
    assert circle.properties["normalized_name"] == "close friends"


def test_wave3_timeline_uses_locked_time_precedence() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    person = service.upsert_node("Person", {"display_name": "Me"})
    old_event = service.upsert_node(
        "Event",
        {"title": "Old event", "source_time": "2022-01-01T10:00:00"},
    )
    precise_event = service.upsert_node(
        "Event",
        {
            "title": "Precise event",
            "resolved_start": "2021-01-01",
            "source_time": "2025-01-01T10:00:00",
        },
    )
    service.upsert_relationship(
        "PARTICIPATED_IN",
        person.properties["id"],
        old_event.properties["id"],
        {},
    )
    service.upsert_relationship(
        "PARTICIPATED_IN",
        person.properties["id"],
        precise_event.properties["id"],
        {},
    )

    timeline = service.get_timeline_for_node(person.properties["id"])

    assert [item.title for item in timeline.items[:2]] == ["Precise event", "Old event"]
    assert timeline.items[0].time_value == "2021-01-01"
    assert timeline.items[0].time_basis == "resolved_start"


def test_wave3_graph_view_hides_archived_and_merged_nodes_by_default() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    seed = service.upsert_node("Person", {"display_name": "Me"})
    visible = service.upsert_node("Event", {"title": "Visible memory"})
    archived = service.upsert_node("Event", {"title": "Archived", "lifecycle_state": "archived"})
    merged = service.upsert_node(
        "Person",
        {"display_name": "Duplicate", "merged_into_id": seed.properties["id"]},
    )
    service.upsert_relationship(
        "PARTICIPATED_IN",
        seed.properties["id"],
        visible.properties["id"],
        {},
    )
    service.upsert_relationship(
        "PARTICIPATED_IN",
        seed.properties["id"],
        archived.properties["id"],
        {},
    )
    service.upsert_relationship("RELATED_TO", seed.properties["id"], merged.properties["id"], {})

    graph_view = service.get_neighborhood_view(seed_id=seed.properties["id"])

    visible_titles = {node.title for node in graph_view.nodes}
    assert "Visible memory" in visible_titles
    assert "Archived" not in visible_titles
    assert "Duplicate" not in visible_titles


def test_wave3_context_package_uses_aliases_and_excludes_noisy_metadata() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    person = service.upsert_node(
        "Person",
        {
            "id": new_uuid(),
            "display_name": "Alessandro",
            "description": "Old friend.",
            "emotional_summary": "Warm past bond with distance now.",
            "metadata": {"raw_score": 0.77},
        },
    )
    source = service.upsert_node(
        "Source",
        {"id": new_uuid(), "source_type": "telegram", "external_id": "msg-1"},
    )
    service.upsert_relationship(
        "MENTIONED_IN",
        person.properties["id"],
        source.properties["id"],
        {"id": new_uuid()},
    )

    package = service.get_context_package(person.properties["id"])

    assert package.target["alias"] == "NODE_000001"
    assert package.target["title"] == "Alessandro"
    assert package.alias_map["NODE_000001"] == person.properties["id"]
    assert "metadata" not in package.target
    assert any(fact["field"] == "emotional_summary" for fact in package.current_facts)


def test_memory_log_service_reads_target_logs_and_detail_buckets() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    person = service.upsert_node("Person", {"display_name": "Marco"})
    place = service.upsert_node("Place", {"name": "Turin"})
    context = service.upsert_node(
        "RelationshipContext",
        {"relationship_detail": "colleague"},
    )
    media = service.upsert_node("MediaAsset", {"media_type": "image", "storage_key": "photo.jpg"})
    log = service.upsert_node(
        "MemoryLog",
        {
            "log_text": "Marco changed job yesterday.",
            "log_kind": "update",
            "host_target_ids": [person.properties["id"]],
            "primary_host_target_id": person.properties["id"],
        },
    )
    service.upsert_relationship(
        "HAS_MEMORY_LOG",
        person.properties["id"],
        log.properties["id"],
        {"primary": True, "role": "primary_host"},
    )
    service.upsert_relationship("INVOLVES", log.properties["id"], place.properties["id"], {})
    service.upsert_relationship(
        "UPDATES_RELATIONSHIP",
        log.properties["id"],
        context.properties["id"],
        {},
    )
    service.upsert_relationship("HAS_MEDIA", log.properties["id"], media.properties["id"], {})

    logs = service.get_memory_logs_for_target(person.properties["id"])
    detail = service.get_memory_log_detail(log.properties["id"])

    assert logs[0].properties["log_text"] == "Marco changed job yesterday."
    assert detail.memory_log.properties["id"] == log.properties["id"]
    assert detail.hosts[0].properties["id"] == person.properties["id"]
    assert detail.involved[0].properties["id"] == place.properties["id"]
    assert detail.relationship_contexts[0].properties["id"] == context.properties["id"]
    assert detail.media_assets[0].properties["id"] == media.properties["id"]


def test_memory_log_service_filters_target_logs() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    person = service.upsert_node("Person", {"display_name": "Marco"})
    place = service.upsert_node("Place", {"name": "Turin"})
    old_log = service.upsert_node(
        "MemoryLog",
        {
            "log_text": "Old note.",
            "log_kind": "note",
            "source_kind": "chat",
            "happened_at": "2024-01-01",
            "host_target_ids": [person.properties["id"]],
            "primary_host_target_id": person.properties["id"],
        },
    )
    matching_log = service.upsert_node(
        "MemoryLog",
        {
            "log_text": "Marco moved to Turin.",
            "log_kind": "update",
            "source_kind": "telegram",
            "happened_at": "2025-01-01",
            "host_target_ids": [person.properties["id"]],
            "primary_host_target_id": person.properties["id"],
            "involved_target_ids": [place.properties["id"]],
            "media_refs": ["photo-1"],
        },
    )
    archived_log = service.upsert_node(
        "MemoryLog",
        {
            "log_text": "Archived note.",
            "log_kind": "update",
            "source_kind": "telegram",
            "happened_at": "2026-01-01",
            "lifecycle_state": "archived",
            "host_target_ids": [person.properties["id"]],
            "primary_host_target_id": person.properties["id"],
            "involved_target_ids": [place.properties["id"]],
            "media_refs": ["photo-2"],
        },
    )
    for log in (old_log, matching_log, archived_log):
        service.upsert_relationship(
            "HAS_MEMORY_LOG",
            person.properties["id"],
            log.properties["id"],
            {"primary": log.properties["id"] == matching_log.properties["id"]},
        )

    logs = service.get_memory_logs_for_target(
        person.properties["id"],
        from_time="2024-06-01",
        to_time="2025-12-31",
        log_kind="update",
        source_kind="telegram",
        involved_target_id=place.properties["id"],
        media_only=True,
    )

    assert [log.properties["id"] for log in logs] == [matching_log.properties["id"]]
    assert (
        service.get_memory_logs_for_target(person.properties["id"], include_archived=True)[0]
        .properties["id"]
        == archived_log.properties["id"]
    )


def test_wave3_map_view_and_analytics_summary() -> None:
    repository = FakeGraphRepository()
    service = GraphService(repository)
    place = service.upsert_node(
        "Place",
        {
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
            "title": "Greek vacation",
            "resolved_start": "2024-08-01",
            "emotion_tags": ["freedom"],
        },
    )
    service.upsert_relationship("HAPPENED_AT", event.properties["id"], place.properties["id"], {})

    map_view = service.get_map_view(city="Athens", country="Greece")
    analytics = service.get_analytics_summary()

    assert map_view.places[0].title == "Athens"
    assert map_view.events[0].title == "Greek vacation"
    assert map_view.timeline[0].title == "Greek vacation"
    assert analytics.node_counts["Place"] == 1
    assert analytics.relationship_counts["HAPPENED_AT"] == 1
    assert analytics.top_emotion_tags[0].key == "freedom"


def _memory_log_time(node: dict[str, object]) -> str:
    properties = node["properties"]
    assert isinstance(properties, dict)
    for key in ("happened_at", "resolved_start", "source_time", "observed_at", "created_at"):
        value = properties.get(key)
        if isinstance(value, str) and value:
            return value
    return ""
