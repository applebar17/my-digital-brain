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
    NeighborhoodResult,
    NodeSearchResult,
    RelationshipResult,
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
