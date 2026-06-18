from __future__ import annotations

from typing import Any

from my_digital_brain.ai.protocols import EmbeddingProvider, ModelRouter
from my_digital_brain.ai.router import EMBEDDING_TASK, StaticModelRouter
from my_digital_brain.ai.schemas import AIRequestContext, EmbeddingRequest
from my_digital_brain.ingestion.contracts import (
    MultiScopeRetrievalResult,
    MultiScopeVectorConfig,
    V1_VECTOR_DIMENSIONS,
    VectorScopeHitRef,
    VectorScopeName,
    VectorScopeSearchRequest,
    default_v1_vector_scope_config,
)
from my_digital_brain.rag.models import VECTOR_STORE_CHROMA, StoredVectorRecord
from my_digital_brain.rag.vector_records import VectorRecordStore
from my_digital_brain.storage.vector import VectorStore

HIDDEN_VECTOR_STATES = {"archived", "deleted", "expired"}


class VectorScopeSearchService:
    """Raw Wave 2 vector search across configured v1 scopes."""

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        vector_record_store: VectorRecordStore,
        model_router: ModelRouter | None = None,
        vector_config: MultiScopeVectorConfig | None = None,
        vector_store_name: str = VECTOR_STORE_CHROMA,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.vector_record_store = vector_record_store
        self.model_router = model_router or StaticModelRouter()
        self.vector_config = vector_config or default_v1_vector_scope_config()
        self.vector_store_name = vector_store_name

    def search(self, request: VectorScopeSearchRequest) -> MultiScopeRetrievalResult:
        enabled_scopes = self._enabled_scopes(request.enabled_scopes)
        route = self.model_router.route(
            EMBEDDING_TASK,
            AIRequestContext(purpose="vector_scope_search"),
        )
        embedding_result = self.embedding_provider.embed(
            EmbeddingRequest(
                texts=[request.query_text],
                model=route.model,
                dimensions=V1_VECTOR_DIMENSIONS,
                context=AIRequestContext(
                    purpose="vector_scope_search",
                    metadata={"scope_count": len(enabled_scopes)},
                ),
                metadata={"route": route.model_dump(mode="json", exclude_none=True)},
            )
        )
        query_embedding = embedding_result.embeddings[0]

        hits: list[VectorScopeHitRef] = []
        for scope in enabled_scopes:
            raw_hits = self.vector_store.search(
                scope.collection,
                query_embedding,
                limit=request.limit_per_scope,
            )
            for raw in raw_hits:
                hit = self._hit_from_raw(scope.scope, scope.collection, raw)
                if hit is not None:
                    hits.append(hit)

        return MultiScopeRetrievalResult(
            query_text=request.query_text,
            dimensions=V1_VECTOR_DIMENSIONS,
            hits=hits,
        )

    def _enabled_scopes(self, requested: list[VectorScopeName]):
        requested_set = set(requested)
        return [
            scope
            for scope in self.vector_config.scopes
            if scope.enabled and (not requested_set or scope.scope in requested_set)
        ]

    def _hit_from_raw(
        self,
        scope: VectorScopeName,
        collection: str,
        raw: dict[str, Any],
    ) -> VectorScopeHitRef | None:
        vector_id = str(raw.get("id") or "")
        if not vector_id:
            return None
        record = self.vector_record_store.get_by_vector_id(
            vector_id,
            vector_store=self.vector_store_name,
            collection=collection,
        )
        if record is None or record.lifecycle_state in HIDDEN_VECTOR_STATES:
            return None
        return VectorScopeHitRef(
            scope=scope,
            collection=collection,
            vector_id=record.vector_id,
            score=_semantic_score(_float_value(raw.get("distance"))),
            primary_target_id=record.primary_target_id,
            primary_target_label=record.primary_target_label,
            canonical_target_id=record.canonical_target_id,
            related_target_ids=record.related_target_ids,
            hit_role=_hit_role(record),
        )


def _semantic_score(distance: float | None) -> float:
    if distance is None:
        return 0.5
    return round(1.0 / (1.0 + max(distance, 0.0)), 6)


def _float_value(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _hit_role(record: StoredVectorRecord):
    if record.hit_role in {"domain_node", "context", "memory_log"}:
        return record.hit_role
    if record.primary_target_label == "MemoryLog":
        return "memory_log"
    if record.primary_target_label in {
        "Claim",
        "Perception",
        "RelationshipContext",
        "RelationshipState",
        "ProfileMemory",
    }:
        return "context"
    return "domain_node"
