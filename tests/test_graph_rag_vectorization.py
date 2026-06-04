from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine

from my_digital_brain.ai.providers.fake import FakeAIProvider
from my_digital_brain.graph.models import NodeSearchResult, RelationshipResult
from my_digital_brain.ingestion.contracts import GraphNodeWrite, GraphWritePlan, IngestionResult
from my_digital_brain.ingestion.enums import IngestionStatus
from my_digital_brain.rag.models import MEMORY_DOCUMENTS_COLLECTION
from my_digital_brain.rag.vector_records import VectorRecordStore
from my_digital_brain.rag.vectorization import GraphVectorizationService
from my_digital_brain.storage.relational import RelationalSessionProvider
from my_digital_brain.storage.relational_models import Base


def test_vectorization_hydrates_graph_embeds_and_persists_vector_record(tmp_path) -> None:
    graph = FakeGraphService(
        nodes=[
            _node(
                "Claim",
                "claim-1",
                text="Alessandro and I were close as teenagers.",
                claim_type="relationship_memory",
                source_ids=["source-1"],
            ),
            _node("Person", "person-1", display_name="Alessandro"),
        ],
        relationships=[
            RelationshipResult(
                type="ABOUT",
                from_id="claim-1",
                to_id="person-1",
                properties={"id": "rel-1"},
            )
        ],
    )
    vector_store = FakeVectorStore()
    record_store = _record_store(tmp_path)
    service = _service(graph, vector_store, record_store)

    result = service.vectorize_ingestion_result(_written_result("claim-1"))

    assert result.status == "ok"
    assert result.documents_built == 1
    assert result.embeddings_upserted == 1
    assert vector_store.upserts[0]["collection"] == MEMORY_DOCUMENTS_COLLECTION
    assert vector_store.upserts[0]["vector_id"] == "memory_documents:claim_summary:claim-1"
    assert vector_store.upserts[0]["metadata"]["primary_target_id"] == "claim-1"
    assert "Claim: Alessandro and I were close as teenagers." in vector_store.upserts[0]["document"]
    records = record_store.list_by_primary_target("claim-1")
    assert records[0].primary_target_label == "Claim"
    assert records[0].related_target_ids == ["person-1"]
    assert records[0].source_ids == ["source-1"]
    assert records[0].embedding_model == "text-embedding-3-small"


def test_vectorization_skips_unchanged_documents(tmp_path) -> None:
    graph = FakeGraphService(
        nodes=[
            _node("Claim", "claim-1", text="Marco moved to Milan.", source_ids=["source-1"]),
        ],
    )
    vector_store = FakeVectorStore()
    record_store = _record_store(tmp_path)
    service = _service(graph, vector_store, record_store)

    first = service.vectorize_ingestion_result(_written_result("claim-1"))
    second = service.vectorize_ingestion_result(_written_result("claim-1"))

    assert first.embeddings_upserted == 1
    assert second.status == "unchanged"
    assert second.unchanged_records == 1
    assert len(vector_store.upserts) == 1


def test_vectorization_archives_existing_record_when_node_is_archived(tmp_path) -> None:
    graph = FakeGraphService(
        nodes=[
            _node("Claim", "claim-1", text="Marco moved to Milan.", source_ids=["source-1"]),
        ],
    )
    vector_store = FakeVectorStore()
    record_store = _record_store(tmp_path)
    service = _service(graph, vector_store, record_store)
    service.vectorize_ingestion_result(_written_result("claim-1"))
    graph.nodes["claim-1"] = _node(
        "Claim",
        "claim-1",
        text="Marco moved to Milan.",
        lifecycle_state="archived",
        source_ids=["source-1"],
    )

    result = service.vectorize_ingestion_result(_written_result("claim-1"))

    assert result.status == "skipped"
    assert result.archived_records == 1
    assert vector_store.deleted == [
        (MEMORY_DOCUMENTS_COLLECTION, "memory_documents:claim_summary:claim-1")
    ]
    assert record_store.list_by_primary_target("claim-1") == []
    assert record_store.list_by_primary_target("claim-1", include_archived=True)[0].lifecycle_state == "archived"


def test_vectorization_archives_existing_record_when_node_no_longer_has_embedding_text(tmp_path) -> None:
    graph = FakeGraphService(
        nodes=[
            _node(
                "Person",
                "person-1",
                display_name="Alessandro",
                description="Teenage friend.",
            ),
        ],
    )
    vector_store = FakeVectorStore()
    record_store = _record_store(tmp_path)
    service = _service(graph, vector_store, record_store)
    service.vectorize_ingestion_result(_written_result("person-1", label="Person"))
    graph.nodes["person-1"] = _node("Person", "person-1", display_name="Alessandro")

    result = service.vectorize_ingestion_result(_written_result("person-1", label="Person"))

    assert result.status == "skipped"
    assert result.archived_records == 1
    assert record_store.list_by_primary_target("person-1") == []


def test_relationship_state_vectorizes_only_when_substantive(tmp_path) -> None:
    graph = FakeGraphService(
        nodes=[
            _node(
                "RelationshipState",
                "state-1",
                description="We became distant after university.",
                status="low_contact",
                original_time_text="after university",
            ),
        ],
    )
    service = _service(graph, FakeVectorStore(), _record_store(tmp_path))

    result = service.vectorize_ingestion_result(_written_result("state-1", label="RelationshipState"))

    assert result.status == "ok"
    assert result.documents_built == 1


class FakeVectorStore:
    def __init__(self) -> None:
        self.upserts: list[dict[str, Any]] = []
        self.deleted: list[tuple[str, str]] = []

    def upsert_embedding(
        self,
        collection: str,
        vector_id: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
        document: str | None = None,
    ) -> None:
        self.upserts.append(
            {
                "collection": collection,
                "vector_id": vector_id,
                "embedding": embedding,
                "metadata": metadata or {},
                "document": document or "",
            }
        )

    def search(self, *_args: object, **_kwargs: object) -> list[dict[str, Any]]:
        return []

    def delete(self, collection: str, vector_id: str) -> None:
        self.deleted.append((collection, vector_id))

    def health_check(self) -> None:
        return None


class FakeGraphService:
    def __init__(
        self,
        *,
        nodes: list[NodeSearchResult],
        relationships: list[RelationshipResult] | None = None,
    ) -> None:
        self.nodes = {node.properties["id"]: node for node in nodes}
        self.relationships = relationships or []

    def get_node(self, node_id: str) -> NodeSearchResult:
        return self.nodes[node_id]

    def get_node_relationships(self, node_id: str, *, limit: int = 50) -> list[RelationshipResult]:
        return [
            relationship
            for relationship in self.relationships
            if relationship.from_id == node_id or relationship.to_id == node_id
        ][:limit]


def _service(
    graph: FakeGraphService,
    vector_store: FakeVectorStore,
    record_store: VectorRecordStore,
) -> GraphVectorizationService:
    return GraphVectorizationService(
        graph_service=graph,
        embedding_provider=FakeAIProvider(embedding_dimensions=4),
        vector_store=vector_store,
        vector_record_store=record_store,
    )


def _written_result(target_id: str, *, label: str = "Claim") -> IngestionResult:
    write = GraphNodeWrite(
        local_ref=f"CANDIDATE_{label.upper()}_001",
        label=label,
        properties={"id": target_id},
    )
    plan_kwargs: dict[str, object] = {"source_id": "source-1"}
    if label == "Claim":
        plan_kwargs["claims_to_create"] = [write]
    elif label == "Perception":
        plan_kwargs["perceptions_to_create"] = [write]
    elif label == "RelationshipContext":
        plan_kwargs["relationship_contexts_to_create"] = [write]
    else:
        plan_kwargs["nodes_to_create"] = [write]
    return IngestionResult(
        source_id="source-1",
        status=IngestionStatus.WRITTEN,
        write_plan=GraphWritePlan(**plan_kwargs),
        metadata={
            "ref_map": {
                f"CANDIDATE_{label.upper()}_001": target_id,
            }
        },
    )


def _node(label: str, node_id: str, **properties: Any) -> NodeSearchResult:
    return NodeSearchResult(label=label, labels=[label], properties={"id": node_id, **properties})


def _record_store(tmp_path) -> VectorRecordStore:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'vectors.sqlite3').as_posix()}", future=True)
    Base.metadata.create_all(engine)
    return VectorRecordStore(RelationalSessionProvider(engine))
