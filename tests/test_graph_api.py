from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from my_digital_brain.api.routes import graph as graph_routes
from my_digital_brain.graph.exceptions import (
    GraphConflictError,
    GraphNotFoundError,
    GraphValidationError,
)
from my_digital_brain.graph.models import (
    AffectiveContextResult,
    EntityDetailResult,
    GraphAnalyticsItem,
    GraphAnalyticsSummary,
    GraphContextPackage,
    GraphViewNode,
    GraphViewRelationship,
    GraphViewResult,
    NeighborhoodResult,
    NodeSearchResult,
    RelationshipContextDetailResult,
    RelationshipResult,
    MapViewResult,
    MemoryLogDetailResult,
    TimelineItem,
    TimelineResult,
)


class FakeGraphService:
    def upsert_node(self, label: str, properties: dict[str, object]) -> NodeSearchResult:
        if label == "Unsafe":
            raise GraphValidationError("bad label")
        if label == "ExternalReference" and properties.get("external_id") == "duplicate":
            raise GraphConflictError("duplicate external reference")
        return NodeSearchResult(
            label=label,
            labels=[label],
            properties={"id": properties.get("id", "node-1"), **properties},
        )

    def patch_node(self, node_id: str, properties: dict[str, object]) -> NodeSearchResult:
        if node_id == "missing":
            raise GraphNotFoundError("missing node")
        return NodeSearchResult(
            label="Person",
            labels=["Person"],
            properties={"id": node_id, **properties},
        )

    def get_node(self, node_id: str) -> NodeSearchResult:
        if node_id == "missing":
            raise GraphNotFoundError("missing node")
        return NodeSearchResult(label="Person", labels=["Person"], properties={"id": node_id})

    def search_nodes(self, **_kwargs: object) -> list[NodeSearchResult]:
        return [NodeSearchResult(label="Topic", labels=["Topic"], properties={"id": "topic-1"})]

    def upsert_relationship(
        self,
        relationship_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, object],
    ) -> RelationshipResult:
        if relationship_type == "UNSAFE":
            raise GraphValidationError("bad relationship")
        return RelationshipResult(
            type=relationship_type,
            from_id=from_id,
            to_id=to_id,
            properties={"id": properties.get("id", "rel-1"), **properties},
        )

    def get_node_relationships(self, *_args: object, **_kwargs: object) -> list[RelationshipResult]:
        return [
            RelationshipResult(
                type="RELATED_TO",
                from_id="node-1",
                to_id="node-2",
                properties={"id": "rel-1"},
            )
        ]

    def get_neighborhood(self, *_args: object, **_kwargs: object) -> NeighborhoodResult:
        return NeighborhoodResult(
            nodes=[
                NodeSearchResult(
                    label="Person",
                    labels=["Person"],
                    properties={"id": "node-1"},
                )
            ],
            relationships=[],
        )

    def get_affective_context(self, node_id: str, **_kwargs: object) -> AffectiveContextResult:
        target = NodeSearchResult(
            label="Place",
            labels=["Place"],
            properties={"id": node_id, "emotional_summary": "Comforting place."},
        )
        perception = NodeSearchResult(
            label="Perception",
            labels=["Perception"],
            properties={"id": "perception-1", "target_type": "Place"},
        )
        return AffectiveContextResult(
            target=target,
            direct_affective_fields={"emotional_summary": "Comforting place."},
            perceptions=[perception],
            relationship_contexts=[],
            affective_relationships=[],
        )

    def create_relationship_state(
        self,
        context_id: str,
        properties: dict[str, object],
        make_current: bool = True,
    ) -> NodeSearchResult:
        return NodeSearchResult(
            label="RelationshipState",
            labels=["RelationshipState"],
            properties={
                "id": "state-1",
                "context_id": context_id,
                "is_current": make_current,
                **properties,
            },
        )

    def get_relationship_states(self, *_args: object, **_kwargs: object) -> list[NodeSearchResult]:
        return [
            NodeSearchResult(
                label="RelationshipState",
                labels=["RelationshipState"],
                properties={"id": "state-1", "status": "low_contact"},
            )
        ]

    def get_relationship_context_detail(
        self,
        context_id: str,
        include_state_history: bool = False,
        **_kwargs: object,
    ) -> RelationshipContextDetailResult:
        return RelationshipContextDetailResult(
            context=NodeSearchResult(
                label="RelationshipContext",
                labels=["RelationshipContext"],
                properties={"id": context_id},
            ),
            state_history=self.get_relationship_states() if include_state_history else [],
        )

    def create_change_record(self, properties: dict[str, object]) -> NodeSearchResult:
        return NodeSearchResult(
            label="ChangeRecord",
            labels=["ChangeRecord"],
            properties={"id": "change-1", **properties},
        )

    def get_change_records_for_target(
        self,
        target_id: str,
        **_kwargs: object,
    ) -> list[NodeSearchResult]:
        return [
            NodeSearchResult(
                label="ChangeRecord",
                labels=["ChangeRecord"],
                properties={"id": "change-1", "target_id": target_id},
            )
        ]

    def transition_node_lifecycle(self, node_id: str, request: object) -> NodeSearchResult:
        return NodeSearchResult(
            label="Person",
            labels=["Person"],
            properties={"id": node_id, "lifecycle_state": request.lifecycle_state},
        )

    def transition_relationship_lifecycle(
        self,
        relationship_id: str,
        request: object,
    ) -> RelationshipResult:
        return RelationshipResult(
            type="RELATED_TO",
            from_id="node-1",
            to_id="node-2",
            properties={"id": relationship_id, "lifecycle_state": request.lifecycle_state},
        )

    def create_contradiction(
        self,
        properties: dict[str, object],
        target_ids: list[str] | None = None,
    ) -> NodeSearchResult:
        return NodeSearchResult(
            label="ContradictionRecord",
            labels=["ContradictionRecord"],
            properties={"id": "contradiction-1", "target_ids": target_ids or [], **properties},
        )

    def query_contradictions(self, **_kwargs: object) -> list[NodeSearchResult]:
        return [
            NodeSearchResult(
                label="ContradictionRecord",
                labels=["ContradictionRecord"],
                properties={"id": "contradiction-1", "status": "detected"},
            )
        ]

    def update_contradiction(
        self,
        contradiction_id: str,
        properties: dict[str, object],
    ) -> NodeSearchResult:
        return NodeSearchResult(
            label="ContradictionRecord",
            labels=["ContradictionRecord"],
            properties={"id": contradiction_id, **properties},
        )

    def create_merge_record(self, **kwargs: object) -> NodeSearchResult:
        return NodeSearchResult(
            label="MergeRecord",
            labels=["MergeRecord"],
            properties={"id": "merge-1", "status": "proposed", **kwargs},
        )

    def query_merges(self, **_kwargs: object) -> list[NodeSearchResult]:
        return [
            NodeSearchResult(
                label="MergeRecord",
                labels=["MergeRecord"],
                properties={"id": "merge-1", "status": "proposed"},
            )
        ]

    def update_merge_record(self, merge_id: str, properties: dict[str, object]) -> NodeSearchResult:
        return NodeSearchResult(
            label="MergeRecord",
            labels=["MergeRecord"],
            properties={"id": merge_id, **properties},
        )

    def apply_merge(self, merge_id: str) -> NodeSearchResult:
        if merge_id == "already-applied":
            raise GraphConflictError("already applied")
        return NodeSearchResult(
            label="MergeRecord",
            labels=["MergeRecord"],
            properties={"id": merge_id, "status": "applied"},
        )

    def get_canonical_node(self, node_id: str) -> NodeSearchResult:
        return NodeSearchResult(
            label="Person",
            labels=["Person"],
            properties={"id": "canonical-for-" + node_id},
        )

    def get_entity_detail(self, node_id: str, **_kwargs: object) -> EntityDetailResult:
        return EntityDetailResult(
            target=NodeSearchResult(
                label="Person",
                labels=["Person"],
                properties={"id": node_id, "display_name": "Marco"},
            ),
            relationships=[],
            perceptions=[],
            relationship_contexts=[],
            sources=[],
            changes=[],
            contradictions=[],
            merges=[],
        )

    def get_memories_for_node(self, node_id: str, **_kwargs: object) -> GraphViewResult:
        return GraphViewResult(
            seed_id=node_id,
            nodes=[
                GraphViewNode(
                    id=node_id,
                    label="Person",
                    title="Marco",
                    lifecycle_state="active",
                )
            ],
            relationships=[],
        )

    def get_memory_logs_for_target(self, target_id: str, **kwargs: object) -> list[NodeSearchResult]:
        self.memory_log_query = {"target_id": target_id, **kwargs}
        return [
            NodeSearchResult(
                label="MemoryLog",
                labels=["MemoryLog"],
                properties={
                    "id": "log-1",
                    "log_text": "Marco moved to Turin.",
                    "log_kind": "update",
                    "source_kind": "telegram",
                    "happened_at": "2025-01-01",
                    "primary_host_target_id": target_id,
                },
            )
        ]

    def get_memory_log_detail(self, log_id: str, **_kwargs: object) -> MemoryLogDetailResult:
        if log_id == "missing":
            raise GraphNotFoundError("MemoryLog not found: missing")
        host = NodeSearchResult(
            label="Person",
            labels=["Person"],
            properties={"id": "node-1", "display_name": "Marco"},
        )
        place = NodeSearchResult(
            label="Place",
            labels=["Place"],
            properties={"id": "place-1", "name": "Turin"},
        )
        context = NodeSearchResult(
            label="RelationshipContext",
            labels=["RelationshipContext"],
            properties={"id": "context-1", "description": "Work relation."},
        )
        media = NodeSearchResult(
            label="MediaAsset",
            labels=["MediaAsset"],
            properties={"id": "media-1", "media_type": "image"},
        )
        return MemoryLogDetailResult(
            memory_log=NodeSearchResult(
                label="MemoryLog",
                labels=["MemoryLog"],
                properties={"id": log_id, "log_text": "Marco moved to Turin."},
            ),
            hosts=[host],
            involved=[place],
            relationship_contexts=[context],
            media_assets=[media],
            relationships=[
                RelationshipResult(
                    type="HAS_MEMORY_LOG",
                    from_id="node-1",
                    to_id=log_id,
                    properties={"id": "rel-log-host"},
                )
            ],
        )

    def get_source_evidence(self, target_id: str, **_kwargs: object) -> list[NodeSearchResult]:
        return [
            NodeSearchResult(
                label="Source",
                labels=["Source"],
                properties={"id": "source-1", "target_id": target_id},
            )
        ]

    def get_timeline_for_node(self, node_id: str, **_kwargs: object) -> TimelineResult:
        return TimelineResult(
            seed=NodeSearchResult(label="Person", labels=["Person"], properties={"id": node_id}),
            items=[
                TimelineItem(
                    id="event-1",
                    label="Event",
                    title="Vacation",
                    time_value="2024-08-01",
                )
            ],
        )

    def get_neighborhood_view(self, seed_id: str, **_kwargs: object) -> GraphViewResult:
        return GraphViewResult(
            seed_id=seed_id,
            nodes=[GraphViewNode(id=seed_id, label="Person", title="Marco")],
            relationships=[
                GraphViewRelationship(
                    id="rel-1",
                    type="RELATED_TO",
                    from_id=seed_id,
                    to_id="node-2",
                )
            ],
        )

    def get_map_view(self, **kwargs: object) -> MapViewResult:
        return MapViewResult(
            seed_id=kwargs.get("seed_id"),
            places=[
                GraphViewNode(
                    id="place-1",
                    label="Place",
                    title="Athens",
                    latitude=37.9838,
                    longitude=23.7275,
                )
            ],
            events=[GraphViewNode(id="event-1", label="Event", title="Vacation")],
            relationships=[],
            timeline=[
                TimelineItem(
                    id="event-1",
                    label="Event",
                    title="Vacation",
                    time_value="2024-08-01",
                )
            ],
        )

    def get_context_package(self, node_id: str, **_kwargs: object) -> GraphContextPackage:
        return GraphContextPackage(
            target={"alias": "NODE_000001", "label": "Person", "title": "Marco"},
            current_facts=[{"field": "description", "value": "Friend"}],
            relationships=[],
            alias_map={"NODE_000001": node_id},
        )

    def get_analytics_summary(self, **_kwargs: object) -> GraphAnalyticsSummary:
        return GraphAnalyticsSummary(
            node_counts={"Person": 1},
            relationship_counts={"RELATED_TO": 1},
            top_connected_nodes=[
                GraphAnalyticsItem(key="node-1", count=1, label="Person: Marco")
            ],
            top_emotion_tags=[GraphAnalyticsItem(key="warmth", count=1)],
            unresolved_contradictions=0,
        )


def client_for(service: FakeGraphService) -> TestClient:
    app = FastAPI()
    app.include_router(graph_routes.router)
    app.dependency_overrides[graph_routes.get_graph_service] = lambda: service
    return TestClient(app)


def test_upsert_node_endpoint() -> None:
    client = client_for(FakeGraphService())

    response = client.post(
        "/graph/nodes",
        json={"label": "Person", "properties": {"display_name": "Marco"}},
    )

    assert response.status_code == 200
    assert response.json()["label"] == "Person"
    assert response.json()["properties"]["display_name"] == "Marco"


def test_patch_node_endpoint() -> None:
    client = client_for(FakeGraphService())

    response = client.patch(
        "/graph/nodes/node-1",
        json={"properties": {"description": "Updated"}},
    )

    assert response.status_code == 200
    assert response.json()["properties"]["description"] == "Updated"


def test_get_and_search_node_endpoints() -> None:
    client = client_for(FakeGraphService())

    get_response = client.get("/graph/nodes/node-1")
    search_response = client.get("/graph/nodes/search?label=Topic&query=graph")

    assert get_response.status_code == 200
    assert get_response.json()["properties"]["id"] == "node-1"
    assert search_response.status_code == 200
    assert search_response.json()[0]["label"] == "Topic"


def test_relationship_endpoint() -> None:
    client = client_for(FakeGraphService())

    response = client.post(
        "/graph/relationships",
        json={
            "type": "RELATED_TO",
            "from_id": "node-1",
            "to_id": "node-2",
            "properties": {"emotional_summary": "Meaningful relation."},
        },
    )

    assert response.status_code == 200
    assert response.json()["type"] == "RELATED_TO"
    assert response.json()["properties"]["emotional_summary"] == "Meaningful relation."


def test_relationships_neighborhood_and_affective_context_endpoints() -> None:
    client = client_for(FakeGraphService())

    relationships = client.get("/graph/nodes/node-1/relationships")
    neighborhood = client.get("/graph/nodes/node-1/neighborhood")
    affective = client.get("/graph/nodes/node-1/affective-context")

    assert relationships.status_code == 200
    assert relationships.json()[0]["type"] == "RELATED_TO"
    assert neighborhood.status_code == 200
    assert neighborhood.json()["nodes"][0]["properties"]["id"] == "node-1"
    assert affective.status_code == 200
    assert affective.json()["direct_affective_fields"]["emotional_summary"] == "Comforting place."
    assert affective.json()["perceptions"][0]["properties"]["target_type"] == "Place"


def test_wave2_relationship_state_and_change_endpoints() -> None:
    client = client_for(FakeGraphService())

    state = client.post(
        "/graph/relationship-contexts/context-1/states",
        json={
            "properties": {"status": "low_contact", "description": "We speak rarely."},
            "make_current": True,
        },
    )
    states = client.get("/graph/relationship-contexts/context-1/states")
    detail = client.get("/graph/relationship-contexts/context-1/detail?include_state_history=true")
    change = client.post(
        "/graph/change-records",
        json={
            "properties": {
                "target_kind": "node",
                "target_id": "node-1",
                "field_path": "lifecycle_state",
            }
        },
    )
    changes = client.get("/graph/targets/node-1/changes?target_kind=node")

    assert state.status_code == 200
    assert state.json()["label"] == "RelationshipState"
    assert states.status_code == 200
    assert detail.json()["state_history"][0]["label"] == "RelationshipState"
    assert change.json()["label"] == "ChangeRecord"
    assert changes.json()[0]["properties"]["target_id"] == "node-1"


def test_wave2_lifecycle_contradiction_and_merge_endpoints() -> None:
    client = client_for(FakeGraphService())

    node_lifecycle = client.post(
        "/graph/nodes/node-1/lifecycle",
        json={"lifecycle_state": "archived", "reason": "merged"},
    )
    relationship_lifecycle = client.post(
        "/graph/relationships/rel-1/lifecycle",
        json={"lifecycle_state": "stale"},
    )
    contradiction = client.post(
        "/graph/contradictions",
        json={
            "properties": {"contradiction_type": "location", "severity": "medium"},
            "target_ids": ["claim-1"],
        },
    )
    contradictions = client.get("/graph/contradictions?status=detected")
    updated_contradiction = client.patch(
        "/graph/contradictions/contradiction-1",
        json={"properties": {"status": "resolved"}},
    )
    merge = client.post(
        "/graph/merges",
        json={
            "canonical_node_id": "person-1",
            "merged_node_ids": ["person-2"],
            "reason": "duplicate",
        },
    )
    merges = client.get("/graph/merges?status=proposed")
    updated_merge = client.patch(
        "/graph/merges/merge-1",
        json={"properties": {"status": "rejected"}},
    )
    applied = client.post("/graph/merges/merge-1/apply")
    canonical = client.get("/graph/nodes/person-2/canonical")

    assert node_lifecycle.json()["properties"]["lifecycle_state"] == "archived"
    assert relationship_lifecycle.json()["properties"]["lifecycle_state"] == "stale"
    assert contradiction.json()["label"] == "ContradictionRecord"
    assert contradictions.json()[0]["properties"]["status"] == "detected"
    assert updated_contradiction.json()["properties"]["status"] == "resolved"
    assert merge.json()["label"] == "MergeRecord"
    assert merges.json()[0]["properties"]["status"] == "proposed"
    assert updated_merge.json()["properties"]["status"] == "rejected"
    assert applied.json()["properties"]["status"] == "applied"
    assert canonical.json()["properties"]["id"] == "canonical-for-person-2"


def test_wave2_conflict_error_mapping() -> None:
    client = client_for(FakeGraphService())

    response = client.post("/graph/merges/already-applied/apply")

    assert response.status_code == 409


def test_wave3_graph_query_endpoints() -> None:
    client = client_for(FakeGraphService())

    detail = client.get("/graph/nodes/node-1/detail?include_history=true")
    memories = client.get("/graph/nodes/node-1/memories")
    evidence = client.get("/graph/targets/node-1/evidence")
    timeline = client.get("/graph/nodes/node-1/timeline")
    neighborhood_view = client.get("/graph/views/neighborhood?seed_id=node-1")
    map_view = client.get("/graph/views/map?city=Athens&country=Greece")
    context_package = client.get("/graph/nodes/node-1/context-package")
    analytics = client.get("/graph/analytics/summary")

    assert detail.json()["target"]["properties"]["display_name"] == "Marco"
    assert memories.json()["nodes"][0]["title"] == "Marco"
    assert evidence.json()[0]["label"] == "Source"
    assert timeline.json()["items"][0]["title"] == "Vacation"
    assert neighborhood_view.json()["relationships"][0]["type"] == "RELATED_TO"
    assert map_view.json()["places"][0]["title"] == "Athens"
    assert context_package.json()["target"]["alias"] == "NODE_000001"
    assert analytics.json()["node_counts"]["Person"] == 1


def test_wave4_memory_log_endpoints() -> None:
    service = FakeGraphService()
    client = client_for(service)

    logs = client.get(
        "/graph/nodes/node-1/memory-logs",
        params={
            "from_time": "2024-01-01",
            "to_time": "2025-12-31",
            "log_kind": "update",
            "source_kind": "telegram",
            "involved_target_id": "place-1",
            "media_only": True,
            "include_archived": True,
            "limit": 12,
        },
    )
    detail = client.get("/graph/memory-logs/log-1")
    missing = client.get("/graph/memory-logs/missing")

    assert logs.status_code == 200
    assert logs.json()[0]["label"] == "MemoryLog"
    assert service.memory_log_query["from_time"] == "2024-01-01"
    assert service.memory_log_query["to_time"] == "2025-12-31"
    assert service.memory_log_query["log_kind"] == "update"
    assert service.memory_log_query["source_kind"] == "telegram"
    assert service.memory_log_query["involved_target_id"] == "place-1"
    assert service.memory_log_query["media_only"] is True
    assert service.memory_log_query["include_archived"] is True
    assert service.memory_log_query["limit"] == 12
    assert detail.status_code == 200
    assert detail.json()["memory_log"]["properties"]["id"] == "log-1"
    assert detail.json()["hosts"][0]["properties"]["id"] == "node-1"
    assert detail.json()["involved"][0]["label"] == "Place"
    assert detail.json()["relationship_contexts"][0]["label"] == "RelationshipContext"
    assert detail.json()["media_assets"][0]["label"] == "MediaAsset"
    assert missing.status_code == 404


def test_graph_api_error_mapping() -> None:
    client = client_for(FakeGraphService())

    validation_response = client.post(
        "/graph/nodes",
        json={"label": "Unsafe", "properties": {}},
    )
    not_found_response = client.get("/graph/nodes/missing")
    conflict_response = client.post(
        "/graph/nodes",
        json={
            "label": "ExternalReference",
            "properties": {"provider": "test", "external_id": "duplicate"},
        },
    )

    assert validation_response.status_code == 400
    assert not_found_response.status_code == 404
    assert conflict_response.status_code == 409
