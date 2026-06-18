from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from my_digital_brain.ai.providers.fake import FakeAIProvider
from my_digital_brain.api.routes import graph as graph_routes
from my_digital_brain.graph.models import (
    GraphContextPackage,
    NeighborhoodResult,
    NodeSearchResult,
    RelationshipResult,
)
from my_digital_brain.ingestion.contracts import MultiScopeRetrievalResult
from my_digital_brain.rag.models import (
    SemanticMemorySearchResult,
    VectorRecordData,
)
from my_digital_brain.rag.search import SemanticMemorySearchService
from my_digital_brain.rag.vector_records import VectorRecordStore
from my_digital_brain.storage.relational import RelationalSessionProvider
from my_digital_brain.storage.relational_models import Base


def test_semantic_search_hydrates_vector_hits_and_expands_graph(tmp_path) -> None:
    graph = FakeSearchGraphService()
    vector_store = FakeSearchVectorStore(
        [
            {
                "id": "memory_contexts:relationship_context_summary:relctx-1",
                "distance": 0.2,
                "document": "Relationship with Alessandro: close teenage friendship, now low contact.",
            }
        ]
    )
    record_store = _record_store(tmp_path)
    record_store.upsert(
        VectorRecordData(
            collection="memory_contexts",
            vector_id="memory_contexts:relationship_context_summary:relctx-1",
            embedding_scope="relationship_context_summary",
            primary_target_id="relctx-1",
            primary_target_label="RelationshipContext",
            related_target_ids=["person-1", "perception-1"],
            source_ids=["source-1"],
            relationship_ids=["relationship-1"],
            hit_role="context",
            embedding_model="text-embedding-3-small",
            builder_version="relationship_context_summary.v1",
            document_checksum="sha256:relctx",
        )
    )

    result = _service(graph, vector_store, record_store).search_semantic(
        "what happened with Alessandro",
        limit=5,
    )

    assert result.mode == "semantic"
    assert result.collection == "scoped"
    assert result.hits[0].scope == "memory_contexts"
    assert result.hits[0].hit_role == "context"
    assert result.hits[0].matched_target_id == "relctx-1"
    assert result.hits[0].display_target_id == "person-1"
    assert result.hits[0].primary_target_id == "person-1"
    assert result.hits[0].primary_target_label == "Person"
    assert result.hits[0].related_target_ids == ["perception-1", "relctx-1"]
    assert result.hits[0].target is not None
    assert result.hits[0].target.title == "Alessandro"
    assert "Relationship with Alessandro" in result.hits[0].document_preview
    assert result.hits[0].matched_records[0]["label"] == "RelationshipContext"
    assert {node.id for node in result.graph_view.nodes} == {"person-1"}
    assert result.context_packages[0].target["id"] == "person-1"
    assert result.context_packages[0].matched_records[0]["label"] == "RelationshipContext"
    assert "query_embedding" in [event.stage for event in result.trace]
    assert "vector_search" in [event.stage for event in result.trace]


def test_semantic_search_does_not_trust_chroma_without_vector_record(tmp_path) -> None:
    result = _service(
        FakeSearchGraphService(),
        FakeSearchVectorStore(
            [
                {
                    "id": "orphan-vector",
                    "distance": 0.1,
                    "document": "This document is not trusted without vector_records.",
                }
            ]
        ),
        _record_store(tmp_path),
    ).search_semantic("Alessandro", limit=5)

    assert result.hits == []
    assert result.graph_view.nodes == []
    assert any(event.stage == "vector_record" and event.status == "skipped" for event in result.trace)


def test_semantic_search_resolves_canonical_identity(tmp_path) -> None:
    graph = FakeSearchGraphService()
    graph.canonical_map["merged-person-1"] = "person-1"
    graph.nodes["merged-person-1"] = _node(
        "Person",
        "merged-person-1",
        display_name="Ale",
        description="Duplicate Alessandro node.",
        merged_into_id="person-1",
    )
    vector_store = FakeSearchVectorStore(
        [{"id": "memory_node_summaries:person_summary:merged-person-1", "distance": 0.3}]
    )
    record_store = _record_store(tmp_path)
    record_store.upsert(
        VectorRecordData(
            collection="memory_node_summaries",
            vector_id="memory_node_summaries:person_summary:merged-person-1",
            embedding_scope="person_summary",
            primary_target_id="merged-person-1",
            primary_target_label="Person",
            hit_role="domain_node",
            builder_version="person_summary.v1",
            document_checksum="sha256:person",
        )
    )

    result = _service(graph, vector_store, record_store).search_semantic("Alessandro")

    assert result.hits[0].canonical_target_id == "person-1"
    assert result.hits[0].canonical_target is not None
    assert result.hits[0].canonical_target.title == "Alessandro"
    assert any(event.stage == "canonical_resolution" for event in result.trace)


def test_hybrid_search_combines_semantic_and_property_matches(tmp_path) -> None:
    graph = FakeSearchGraphService()
    vector_store = FakeSearchVectorStore(
        [{"id": "memory_contexts:perception_summary:perception-1", "distance": 0.15}]
    )
    record_store = _record_store(tmp_path)
    record_store.upsert(
        VectorRecordData(
            collection="memory_contexts",
            vector_id="memory_contexts:perception_summary:perception-1",
            embedding_scope="perception_summary",
            primary_target_id="perception-1",
            primary_target_label="Perception",
            related_target_ids=["person-1"],
            hit_role="context",
            builder_version="perception_summary.v1",
            document_checksum="sha256:perception",
        )
    )

    result = _service(graph, vector_store, record_store).search_hybrid("Alessandro", limit=5)

    assert result.mode == "hybrid"
    assert result.hits[0].source == "semantic"
    assert result.hits[0].matched_target_id == "perception-1"
    assert result.hits[0].display_target_id == "person-1"
    assert any(event.stage == "property_search" for event in result.trace)


def test_memory_log_hit_folds_to_host_but_preserves_matched_record(tmp_path) -> None:
    graph = FakeSearchGraphService()
    vector_store = FakeSearchVectorStore(
        [
            {
                "id": "memory_micro_logs:memory_log_summary:memory-log-1",
                "distance": 0.05,
                "document": "I felt pressured by Alessandro during the dinner.",
            }
        ]
    )
    record_store = _record_store(tmp_path)
    record_store.upsert(
        VectorRecordData(
            collection="memory_micro_logs",
            vector_id="memory_micro_logs:memory_log_summary:memory-log-1",
            embedding_scope="memory_log_summary",
            primary_target_id="memory-log-1",
            primary_target_label="MemoryLog",
            canonical_target_id="person-1",
            related_target_ids=["person-1", "relctx-1"],
            source_ids=["source-1"],
            hit_role="memory_log",
            builder_version="memory_log_summary.v1",
            document_checksum="sha256:memory-log",
        )
    )

    result = _service(graph, vector_store, record_store).search_semantic(
        "pressured by Alessandro",
        limit=5,
    )

    assert result.hits[0].scope == "memory_micro_logs"
    assert result.hits[0].hit_role == "memory_log"
    assert result.hits[0].matched_target_id == "memory-log-1"
    assert result.hits[0].display_target_id == "person-1"
    assert result.hits[0].matched_records[0]["label"] == "MemoryLog"
    assert result.context_packages[0].matched_records[0]["label"] == "MemoryLog"
    assert "memory-log-1" not in {node.id for node in result.graph_view.nodes}
    assert {node.id for node in result.graph_view.nodes} == {"person-1"}


def test_target_constraints_filter_hits_by_expanded_graph_context(tmp_path) -> None:
    graph = FakeSearchGraphService()
    vector_store = FakeSearchVectorStore(
        [
            {"id": "memory_contexts:perception_summary:perception-1", "distance": 0.02},
            {"id": "memory_contexts:claim_summary:claim-1", "distance": 0.01},
        ]
    )
    record_store = _record_store(tmp_path)
    record_store.upsert(
        VectorRecordData(
            collection="memory_contexts",
            vector_id="memory_contexts:perception_summary:perception-1",
            embedding_scope="perception_summary",
            primary_target_id="perception-1",
            primary_target_label="Perception",
            related_target_ids=["person-1"],
            hit_role="context",
            builder_version="perception_summary.v1",
            document_checksum="sha256:perception",
        )
    )
    record_store.upsert(
        VectorRecordData(
            collection="memory_contexts",
            vector_id="memory_contexts:claim_summary:claim-1",
            embedding_scope="claim_summary",
            primary_target_id="claim-1",
            primary_target_label="Claim",
            hit_role="context",
            builder_version="claim_summary.v1",
            document_checksum="sha256:claim",
        )
    )

    result = _service(graph, vector_store, record_store).search_semantic(
        "oppressive",
        target_ids=["person-1"],
        limit=5,
    )

    assert [hit.matched_target_id for hit in result.hits] == ["perception-1"]
    assert result.hits[0].display_target_id == "person-1"
    assert any(event.stage == "target_expansion" for event in result.trace)
    target_filter = next(event for event in result.trace if event.stage == "target_filter")
    assert target_filter.data["before_count"] == 2
    assert target_filter.data["after_count"] == 1


def test_search_can_focus_rendered_graph_without_narrowing_retrieval_hits(tmp_path) -> None:
    graph = FakeSearchGraphService()
    vector_store = FakeSearchVectorStore(
        [
            {"id": "memory_contexts:relationship_context_summary:relctx-1", "distance": 0.02},
            {"id": "memory_contexts:claim_summary:claim-1", "distance": 1.3},
        ]
    )
    record_store = _record_store(tmp_path)
    record_store.upsert(
        VectorRecordData(
            collection="memory_contexts",
            vector_id="memory_contexts:relationship_context_summary:relctx-1",
            embedding_scope="relationship_context_summary",
            primary_target_id="relctx-1",
            primary_target_label="RelationshipContext",
            related_target_ids=["person-1"],
            source_ids=["source-1"],
            relationship_ids=["relationship-1"],
            hit_role="context",
            embedding_model="text-embedding-3-small",
            builder_version="relationship_context_summary.v1",
            document_checksum="sha256:relctx",
        )
    )
    record_store.upsert(
        VectorRecordData(
            collection="memory_contexts",
            vector_id="memory_contexts:claim_summary:claim-1",
            embedding_scope="claim_summary",
            primary_target_id="claim-1",
            primary_target_label="Claim",
            hit_role="context",
            builder_version="claim_summary.v1",
            document_checksum="sha256:claim",
        )
    )

    result = _service(graph, vector_store, record_store).search_semantic(
        "mio fratello",
        graph_focus="adaptive",
        limit=5,
    )

    assert [hit.primary_target_id for hit in result.hits] == ["person-1", "claim-1"]
    assert {node.id for node in result.graph_view.nodes} == {"person-1"}
    trace = next(event for event in result.trace if event.stage == "graph_assembly")
    assert trace.data["focus_mode"] == "adaptive"
    assert trace.data["focus_algorithm"] == "otsu"
    assert trace.data["selected_target_ids"] == ["person-1"]
    assert trace.data["excluded_target_ids"] == ["claim-1"]


def test_adaptive_search_graph_keeps_isolated_focus_hit_visible(tmp_path) -> None:
    graph = FakeSearchGraphService()
    vector_store = FakeSearchVectorStore(
        [{"id": "memory_contexts:claim_summary:claim-1", "distance": 0.02}]
    )
    record_store = _record_store(tmp_path)
    record_store.upsert(
        VectorRecordData(
            collection="memory_contexts",
            vector_id="memory_contexts:claim_summary:claim-1",
            embedding_scope="claim_summary",
            primary_target_id="claim-1",
            primary_target_label="Claim",
            hit_role="context",
            builder_version="claim_summary.v1",
            document_checksum="sha256:claim",
        )
    )

    result = _service(graph, vector_store, record_store).search_semantic(
        "Marco",
        graph_focus="adaptive",
        limit=5,
    )

    assert [hit.primary_target_id for hit in result.hits] == ["claim-1"]
    assert [node.id for node in result.graph_view.nodes] == ["claim-1"]
    assert result.graph_view.relationships == []


def test_hidden_vector_records_are_excluded_by_default(tmp_path) -> None:
    vector_store = FakeSearchVectorStore(
        [{"id": "memory_contexts:claim_summary:claim-1", "distance": 0.1}]
    )
    record_store = _record_store(tmp_path)
    record_store.upsert(
        VectorRecordData(
            collection="memory_contexts",
            vector_id="memory_contexts:claim_summary:claim-1",
            embedding_scope="claim_summary",
            primary_target_id="claim-1",
            primary_target_label="Claim",
            hit_role="context",
            builder_version="claim_summary.v1",
            document_checksum="sha256:claim",
            lifecycle_state="archived",
        )
    )

    result = _service(FakeSearchGraphService(), vector_store, record_store).search_semantic("Marco")

    assert result.hits == []
    assert any(event.data.get("lifecycle_state") == "archived" for event in result.trace)


def test_graph_semantic_search_api_uses_search_dependency(tmp_path) -> None:
    app = FastAPI()
    app.include_router(graph_routes.router)
    service = StaticSemanticSearchService()
    app.dependency_overrides[graph_routes.get_semantic_search_service] = lambda: service
    client = TestClient(app)

    response = client.get(
        "/graph/search/semantic",
        params=[
            ("query", "Alessandro"),
            ("target_ids", "person-1"),
            ("target_ids", "relctx-1"),
        ],
    )

    assert response.status_code == 200
    assert response.json()["query"] == "Alessandro"
    assert service.semantic_queries == ["Alessandro"]
    assert service.semantic_kwargs[0]["target_ids"] == ["person-1", "relctx-1"]


def test_graph_hybrid_search_api_uses_search_dependency() -> None:
    app = FastAPI()
    app.include_router(graph_routes.router)
    service = StaticSemanticSearchService()
    app.dependency_overrides[graph_routes.get_semantic_search_service] = lambda: service
    client = TestClient(app)

    response = client.get("/graph/search/hybrid", params={"query": "Alessandro", "label": "Person"})

    assert response.status_code == 200
    assert response.json()["mode"] == "hybrid"
    assert service.hybrid_queries == [("Alessandro", "Person")]


def test_graph_vector_scope_search_api_uses_search_dependency() -> None:
    app = FastAPI()
    app.include_router(graph_routes.router)
    service = StaticVectorScopeSearchService()
    app.dependency_overrides[graph_routes.get_vector_scope_search_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/graph/search/vector-scopes",
        json={"query_text": "Alessandro", "limit_per_scope": 5},
    )

    assert response.status_code == 200
    assert response.json()["query_text"] == "Alessandro"
    assert service.queries == ["Alessandro"]


class FakeSearchVectorStore:
    def __init__(self, hits: list[dict[str, Any]]) -> None:
        self.hits = hits
        self.search_calls: list[dict[str, Any]] = []

    def search(
        self,
        collection: str,
        embedding: list[float],
        limit: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.search_calls.append(
            {"collection": collection, "embedding": embedding, "limit": limit, "where": where}
        )
        return self.hits[:limit]

    def upsert_embedding(self, *_args: object, **_kwargs: object) -> None:
        return None

    def delete(self, *_args: object, **_kwargs: object) -> None:
        return None

    def health_check(self) -> None:
        return None


class FakeSearchGraphService:
    def __init__(self) -> None:
        self.nodes: dict[str, NodeSearchResult] = {
            "person-1": _node(
                "Person",
                "person-1",
                display_name="Alessandro",
                description="Teenage friend, now low contact.",
                source_ids=["source-1"],
            ),
            "relctx-1": _node(
                "RelationshipContext",
                "relctx-1",
                description="Close teenage friendship, now low contact.",
                emotional_summary="Care mixed with distance.",
                source_ids=["source-1"],
            ),
            "perception-1": _node(
                "Perception",
                "perception-1",
                description="The user felt Alessandro's personality was oppressive.",
                emotional_summary="Discomfort and pressure.",
            ),
            "memory-log-1": _node(
                "MemoryLog",
                "memory-log-1",
                log_text="I felt pressured by Alessandro during the dinner.",
                log_kind="experience",
                source_kind="chat",
                primary_host_target_id="person-1",
            ),
            "claim-1": _node("Claim", "claim-1", text="Marco moved to Milan."),
        }
        self.relationships = [
            RelationshipResult(
                type="HAS_RELATIONSHIP_CONTEXT",
                from_id="person-1",
                to_id="relctx-1",
                properties={"id": "relationship-1"},
            ),
            RelationshipResult(
                type="PERCEPTION_OF",
                from_id="perception-1",
                to_id="person-1",
                properties={"id": "relationship-2"},
            ),
        ]
        self.canonical_map: dict[str, str] = {}

    def get_node(self, node_id: str) -> NodeSearchResult:
        return self.nodes[node_id]

    def get_canonical_node(self, node_id: str) -> NodeSearchResult:
        return self.nodes[self.canonical_map.get(node_id, node_id)]

    def get_neighborhood(self, node_id: str, *, depth: int = 1, limit: int = 50) -> NeighborhoodResult:
        node_ids = {node_id}
        relationships = [
            relationship
            for relationship in self.relationships
            if relationship.from_id == node_id or relationship.to_id == node_id
        ][:limit]
        for relationship in relationships:
            node_ids.add(relationship.from_id)
            node_ids.add(relationship.to_id)
        return NeighborhoodResult(
            nodes=[self.nodes[item] for item in node_ids if item in self.nodes],
            relationships=relationships,
        )

    def get_context_package(self, node_id: str, **_kwargs: object) -> GraphContextPackage:
        node = self.nodes[node_id]
        return GraphContextPackage(
            target={
                "id": node_id,
                "label": node.label,
                "title": _title(node),
                "description": node.properties.get("description"),
            },
            current_facts=[],
            relationships=[],
            evidence=[{"source_ids": node.properties.get("source_ids", [])}],
        )

    def search_nodes(self, *, label: str | None = None, query: str | None = None, limit: int = 25, **_kwargs: object) -> list[NodeSearchResult]:
        normalized = str(query or "").lower()
        matches = []
        for node in self.nodes.values():
            if label and node.label != label:
                continue
            if normalized in str(node.properties).lower():
                matches.append(node)
        return matches[:limit]


class StaticSemanticSearchService:
    def __init__(self) -> None:
        self.semantic_queries: list[str] = []
        self.hybrid_queries: list[tuple[str, str | None]] = []
        self.semantic_kwargs: list[dict[str, object]] = []
        self.hybrid_kwargs: list[dict[str, object]] = []

    def search_semantic(self, query: str, **_kwargs: object) -> SemanticMemorySearchResult:
        self.semantic_queries.append(query)
        self.semantic_kwargs.append(_kwargs)
        return _empty_search_result(query, mode="semantic")

    def search_hybrid(self, query: str, label: str | None = None, **_kwargs: object) -> SemanticMemorySearchResult:
        self.hybrid_queries.append((query, label))
        self.hybrid_kwargs.append(_kwargs)
        return _empty_search_result(query, mode="hybrid")


class StaticVectorScopeSearchService:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(self, request) -> MultiScopeRetrievalResult:
        self.queries.append(request.query_text)
        return MultiScopeRetrievalResult(query_text=request.query_text)


def _service(
    graph: FakeSearchGraphService,
    vector_store: FakeSearchVectorStore,
    record_store: VectorRecordStore,
) -> SemanticMemorySearchService:
    return SemanticMemorySearchService(
        graph_service=graph,
        embedding_provider=FakeAIProvider(embedding_dimensions=4),
        vector_store=vector_store,
        vector_record_store=record_store,
    )


def _node(label: str, node_id: str, **properties: Any) -> NodeSearchResult:
    return NodeSearchResult(label=label, labels=[label], properties={"id": node_id, **properties})


def _title(node: NodeSearchResult) -> str:
    return str(
        node.properties.get("display_name")
        or node.properties.get("name")
        or node.properties.get("title")
        or node.properties.get("text")
        or node.properties.get("description")
        or node.properties["id"]
    )


def _record_store(tmp_path) -> VectorRecordStore:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'semantic.sqlite3').as_posix()}", future=True)
    Base.metadata.create_all(engine)
    return VectorRecordStore(RelationalSessionProvider(engine))


def _empty_search_result(query: str, *, mode: str) -> SemanticMemorySearchResult:
    return SemanticMemorySearchResult(
        query=query,
        mode=mode,
        graph_view={"seed_id": "", "nodes": [], "relationships": []},
    )
