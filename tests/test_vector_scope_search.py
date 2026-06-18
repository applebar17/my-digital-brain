from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine

from my_digital_brain.ai.schemas import EmbeddingRequest, EmbeddingResult, ProviderCallMetadata
from my_digital_brain.ingestion.contracts import (
    VectorScopeName,
    VectorScopeSearchRequest,
)
from my_digital_brain.rag.models import VectorRecordData
from my_digital_brain.rag.scoped_search import VectorScopeSearchService
from my_digital_brain.rag.vector_records import VectorRecordStore
from my_digital_brain.storage.relational import RelationalSessionProvider
from my_digital_brain.storage.relational_models import Base


def test_vector_scope_search_embeds_once_and_searches_all_enabled_scopes(tmp_path) -> None:
    provider = TrackingEmbeddingProvider()
    vector_store = FakeScopedVectorStore(
        {
            "memory_node_summaries": [
                {"id": "memory_node_summaries:person_summary:person-1", "distance": 0.1}
            ],
            "memory_contexts": [
                {"id": "memory_contexts:claim_summary:claim-1", "distance": 0.2}
            ],
            "memory_micro_logs": [
                {"id": "memory_micro_logs:memory_log_summary:log-1", "distance": 0.3}
            ],
        }
    )
    record_store = _record_store(tmp_path)
    record_store.upsert(
        VectorRecordData(
            collection="memory_node_summaries",
            vector_id="memory_node_summaries:person_summary:person-1",
            embedding_scope="person_summary",
            primary_target_id="person-1",
            primary_target_label="Person",
            builder_version="person_summary.v1",
            document_checksum="sha256:person",
            hit_role="domain_node",
        )
    )
    record_store.upsert(
        VectorRecordData(
            collection="memory_contexts",
            vector_id="memory_contexts:claim_summary:claim-1",
            embedding_scope="claim_summary",
            primary_target_id="claim-1",
            primary_target_label="Claim",
            builder_version="claim_summary.v1",
            document_checksum="sha256:claim",
            hit_role="context",
        )
    )
    record_store.upsert(
        VectorRecordData(
            collection="memory_micro_logs",
            vector_id="memory_micro_logs:memory_log_summary:log-1",
            embedding_scope="memory_log_summary",
            primary_target_id="log-1",
            primary_target_label="MemoryLog",
            canonical_target_id="person-1",
            related_target_ids=["person-1"],
            builder_version="memory_log_summary.v1",
            document_checksum="sha256:log",
            hit_role="memory_log",
        )
    )

    result = VectorScopeSearchService(
        embedding_provider=provider,
        vector_store=vector_store,
        vector_record_store=record_store,
    ).search(VectorScopeSearchRequest(query_text="Marco changed job", limit_per_scope=5))

    assert len(provider.requests) == 1
    assert provider.requests[0].dimensions == 512
    assert [call["collection"] for call in vector_store.search_calls] == [
        "memory_node_summaries",
        "memory_contexts",
        "memory_micro_logs",
    ]
    assert all(len(call["embedding"]) == 512 for call in vector_store.search_calls)
    assert [hit.scope for hit in result.hits] == [
        VectorScopeName.MEMORY_NODE_SUMMARIES,
        VectorScopeName.MEMORY_CONTEXTS,
        VectorScopeName.MEMORY_MICRO_LOGS,
    ]
    assert [hit.hit_role for hit in result.hits] == ["domain_node", "context", "memory_log"]
    assert result.hits[2].canonical_target_id == "person-1"


def test_vector_scope_search_respects_requested_scopes_and_skips_orphans(tmp_path) -> None:
    provider = TrackingEmbeddingProvider()
    vector_store = FakeScopedVectorStore(
        {
            "memory_micro_logs": [
                {"id": "orphan-vector", "distance": 0.1},
                {"id": "memory_micro_logs:memory_log_summary:log-1", "distance": 0.2},
            ],
        }
    )
    record_store = _record_store(tmp_path)
    record_store.upsert(
        VectorRecordData(
            collection="memory_micro_logs",
            vector_id="memory_micro_logs:memory_log_summary:log-1",
            embedding_scope="memory_log_summary",
            primary_target_id="log-1",
            primary_target_label="MemoryLog",
            builder_version="memory_log_summary.v1",
            document_checksum="sha256:log",
            hit_role="memory_log",
        )
    )

    result = VectorScopeSearchService(
        embedding_provider=provider,
        vector_store=vector_store,
        vector_record_store=record_store,
    ).search(
        VectorScopeSearchRequest(
            query_text="Marco changed job",
            enabled_scopes=[VectorScopeName.MEMORY_MICRO_LOGS],
        )
    )

    assert [call["collection"] for call in vector_store.search_calls] == ["memory_micro_logs"]
    assert [hit.vector_id for hit in result.hits] == [
        "memory_micro_logs:memory_log_summary:log-1"
    ]


class TrackingEmbeddingProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self.requests: list[EmbeddingRequest] = []

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        self.requests.append(request)
        dimensions = request.dimensions or 3
        return EmbeddingResult(
            embeddings=[[0.1 for _ in range(dimensions)] for _ in request.texts],
            metadata=ProviderCallMetadata.fake(model=request.model or "fake-embedding-model"),
        )


class FakeScopedVectorStore:
    def __init__(self, hits_by_collection: dict[str, list[dict[str, Any]]]) -> None:
        self.hits_by_collection = hits_by_collection
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
        return list(self.hits_by_collection.get(collection, []))[:limit]

    def upsert_embedding(self, *_args: object, **_kwargs: object) -> None:
        return None

    def delete(self, *_args: object, **_kwargs: object) -> None:
        return None

    def health_check(self) -> None:
        return None


def _record_store(tmp_path) -> VectorRecordStore:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'scope-search.sqlite3').as_posix()}", future=True)
    Base.metadata.create_all(engine)
    return VectorRecordStore(RelationalSessionProvider(engine))
