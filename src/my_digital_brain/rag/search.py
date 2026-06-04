from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import Any, Literal

from my_digital_brain.ai.logging import log_event
from my_digital_brain.ai.protocols import EmbeddingProvider, ModelRouter
from my_digital_brain.ai.router import EMBEDDING_TASK, StaticModelRouter
from my_digital_brain.ai.schemas import AIRequestContext, EmbeddingRequest
from my_digital_brain.graph.models import (
    GraphContextPackage,
    GraphViewResult,
    NeighborhoodResult,
    NodeSearchResult,
    RelationshipResult,
)
from my_digital_brain.graph.projection import GraphProjection
from my_digital_brain.rag.models import (
    MEMORY_DOCUMENTS_COLLECTION,
    VECTOR_STORE_CHROMA,
    SemanticMemoryHit,
    SemanticMemorySearchResult,
    SemanticSearchTraceEvent,
    StoredVectorRecord,
)
from my_digital_brain.rag.vector_records import VectorRecordStore
from my_digital_brain.storage.vector import VectorStore

logger = logging.getLogger(__name__)

HIDDEN_VECTOR_STATES = {"archived", "deleted", "expired"}


class SemanticMemorySearchService:
    """Graph-grounded semantic and hybrid retrieval over Chroma + Neo4j."""

    def __init__(
        self,
        *,
        graph_service: Any,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        vector_record_store: VectorRecordStore,
        model_router: ModelRouter | None = None,
        projection: GraphProjection | None = None,
        collection: str = MEMORY_DOCUMENTS_COLLECTION,
        vector_store_name: str = VECTOR_STORE_CHROMA,
    ) -> None:
        self.graph_service = graph_service
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.vector_record_store = vector_record_store
        self.model_router = model_router or StaticModelRouter()
        self.projection = projection or GraphProjection()
        self.collection = collection
        self.vector_store_name = vector_store_name

    def search_semantic(
        self,
        query: str,
        *,
        limit: int = 10,
        include_archived: bool = False,
        include_history: bool = False,
    ) -> SemanticMemorySearchResult:
        return self._search(
            query,
            mode="semantic",
            limit=limit,
            include_archived=include_archived,
            include_history=include_history,
        )

    def search_hybrid(
        self,
        query: str,
        *,
        label: str | None = None,
        limit: int = 10,
        include_archived: bool = False,
        include_history: bool = False,
    ) -> SemanticMemorySearchResult:
        return self._search(
            query,
            mode="hybrid",
            label=label,
            limit=limit,
            include_archived=include_archived,
            include_history=include_history,
        )

    def _search(
        self,
        query: str,
        *,
        mode: Literal["semantic", "hybrid"],
        label: str | None = None,
        limit: int,
        include_archived: bool,
        include_history: bool,
    ) -> SemanticMemorySearchResult:
        query = _clean_query(query)
        limit = _bounded_limit(limit)
        trace: list[SemanticSearchTraceEvent] = []
        route = self.model_router.route(
            EMBEDDING_TASK,
            AIRequestContext(purpose="semantic_memory_search"),
        )
        embedding_result = self.embedding_provider.embed(
            EmbeddingRequest(
                texts=[query],
                model=route.model,
                context=AIRequestContext(purpose="semantic_memory_search"),
                metadata={"route": route.model_dump(mode="json", exclude_none=True)},
            )
        )
        query_embedding = embedding_result.embeddings[0]
        trace.append(
            _trace(
                "query_embedding",
                "Embedded query for vector search.",
                model=route.model,
                provider=route.provider,
                dimension_count=len(query_embedding),
            )
        )

        raw_hits = self.vector_store.search(
            self.collection,
            query_embedding,
            limit=max(limit * 3, limit),
        )
        trace.append(
            _trace(
                "vector_search",
                "Chroma returned semantic vector candidates.",
                collection=self.collection,
                raw_hit_count=len(raw_hits),
            )
        )

        hits = self._semantic_hits(
            raw_hits,
            include_archived=include_archived,
            trace=trace,
        )
        if mode == "hybrid":
            hits.extend(
                self._property_hits(
                    query,
                    label=label,
                    include_archived=include_archived,
                    limit=limit,
                    trace=trace,
                )
            )

        hits = self._dedupe_and_rank_hits(hits, limit=limit)
        neighborhoods = self._expanded_neighborhood(hits, include_archived=include_archived)
        graph_view = self.projection.to_graph_view_result(
            seed_id=hits[0].primary_target_id if hits else "",
            neighborhood=neighborhoods,
            include_history=include_history,
            include_archived=include_archived,
        )
        context_packages = self._context_packages(hits, limit=min(limit, 5), trace=trace)
        trace.append(
            _trace(
                "ranking",
                "Ranked hydrated graph-grounded hits.",
                hit_count=len(hits),
                graph_node_count=len(graph_view.nodes),
                graph_relationship_count=len(graph_view.relationships),
                context_package_count=len(context_packages),
            )
        )
        log_event(
            logger,
            "rag.semantic_search.done",
            component="rag",
            mode=mode,
            hit_count=len(hits),
            graph_node_count=len(graph_view.nodes),
            graph_relationship_count=len(graph_view.relationships),
        )
        return SemanticMemorySearchResult(
            query=query,
            mode=mode,
            collection=self.collection,
            hits=hits,
            graph_view=graph_view,
            context_packages=context_packages,
            trace=trace,
        )

    def _semantic_hits(
        self,
        raw_hits: list[dict[str, Any]],
        *,
        include_archived: bool,
        trace: list[SemanticSearchTraceEvent],
    ) -> list[SemanticMemoryHit]:
        hits: list[SemanticMemoryHit] = []
        for raw in raw_hits:
            vector_id = str(raw.get("id") or "")
            if not vector_id:
                continue
            record = self.vector_record_store.get_by_vector_id(
                vector_id,
                vector_store=self.vector_store_name,
                collection=self.collection,
            )
            if record is None:
                trace.append(
                    _trace(
                        "vector_record",
                        "Skipped Chroma hit without relational vector record.",
                        status="skipped",
                        vector_id=vector_id,
                    )
                )
                continue
            if not include_archived and record.lifecycle_state in HIDDEN_VECTOR_STATES:
                trace.append(
                    _trace(
                        "vector_record",
                        "Skipped hidden vector record.",
                        status="skipped",
                        vector_id=vector_id,
                        lifecycle_state=record.lifecycle_state,
                    )
                )
                continue
            target, canonical = self._hydrate_target(record.primary_target_id, trace=trace)
            if target is None:
                continue
            if not include_archived and self.projection.is_hidden_node(canonical or target):
                continue
            related_targets = self._hydrate_related(record.related_target_ids, trace=trace)
            distance = _float_value(raw.get("distance"))
            score = _semantic_score(distance)
            score += _graph_boost(canonical or target, record=record)
            hit = SemanticMemoryHit(
                rank=0,
                score=round(score, 6),
                source="semantic",
                vector_id=record.vector_id,
                distance=distance,
                collection=record.collection,
                embedding_scope=record.embedding_scope,
                primary_target_id=target.properties["id"],
                primary_target_label=target.label,
                canonical_target_id=(
                    canonical.properties["id"]
                    if canonical and canonical.properties["id"] != target.properties["id"]
                    else None
                ),
                related_target_ids=_dedupe(
                    [node.properties["id"] for node in related_targets]
                    or record.related_target_ids
                ),
                source_ids=record.source_ids,
                relationship_ids=record.relationship_ids,
                title=self.projection.display_title(canonical or target),
                description=self.projection.display_description(canonical or target),
                document_preview=_preview(raw.get("document")),
                target=self.projection.to_graph_view_node(target),
                canonical_target=(
                    self.projection.to_graph_view_node(canonical)
                    if canonical is not None
                    else None
                ),
                debug={
                    "semantic_score": _semantic_score(distance),
                    "graph_boost": _graph_boost(canonical or target, record=record),
                    "record_lifecycle_state": record.lifecycle_state,
                },
            )
            hits.append(hit)
        return hits

    def _property_hits(
        self,
        query: str,
        *,
        label: str | None,
        include_archived: bool,
        limit: int,
        trace: list[SemanticSearchTraceEvent],
    ) -> list[SemanticMemoryHit]:
        try:
            nodes = self.graph_service.search_nodes(label=label, query=query, limit=limit)
        except Exception as exc:
            trace.append(
                _trace(
                    "property_search",
                    "Property search failed.",
                    status="error",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            )
            return []
        hits: list[SemanticMemoryHit] = []
        for node in nodes:
            canonical = self._canonical_for_node(node, trace=trace)
            target = canonical or node
            if not include_archived and self.projection.is_hidden_node(target):
                continue
            score = 0.7 + _graph_boost(target, record=None)
            hits.append(
                SemanticMemoryHit(
                    rank=0,
                    score=round(score, 6),
                    source="property",
                    primary_target_id=node.properties["id"],
                    primary_target_label=node.label,
                    canonical_target_id=(
                        canonical.properties["id"]
                        if canonical and canonical.properties["id"] != node.properties["id"]
                        else None
                    ),
                    related_target_ids=[],
                    source_ids=list(node.properties.get("source_ids", [])),
                    title=self.projection.display_title(target),
                    description=self.projection.display_description(target),
                    target=self.projection.to_graph_view_node(node),
                    canonical_target=(
                        self.projection.to_graph_view_node(canonical)
                        if canonical is not None
                        else None
                    ),
                    debug={"property_match": True, "graph_boost": _graph_boost(target, record=None)},
                )
            )
        trace.append(
            _trace(
                "property_search",
                "Hydrated exact/property graph matches for hybrid retrieval.",
                hit_count=len(hits),
            )
        )
        return hits

    def _hydrate_target(
        self,
        target_id: str,
        *,
        trace: list[SemanticSearchTraceEvent],
    ) -> tuple[NodeSearchResult | None, NodeSearchResult | None]:
        try:
            target = self.graph_service.get_node(target_id)
        except Exception as exc:
            trace.append(
                _trace(
                    "graph_hydration",
                    "Could not hydrate primary graph target.",
                    status="skipped",
                    target_id=target_id,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            )
            return None, None
        canonical = self._canonical_for_node(target, trace=trace)
        return target, canonical

    def _canonical_for_node(
        self,
        node: NodeSearchResult,
        *,
        trace: list[SemanticSearchTraceEvent],
    ) -> NodeSearchResult | None:
        if not hasattr(self.graph_service, "get_canonical_node"):
            return None
        node_id = node.properties["id"]
        try:
            canonical = self.graph_service.get_canonical_node(node_id)
        except Exception:
            return None
        if canonical.properties["id"] != node_id:
            trace.append(
                _trace(
                    "canonical_resolution",
                    "Resolved merged node to canonical target.",
                    node_id=node_id,
                    canonical_id=canonical.properties["id"],
                )
            )
        return canonical

    def _hydrate_related(
        self,
        related_target_ids: list[str],
        *,
        trace: list[SemanticSearchTraceEvent],
    ) -> list[NodeSearchResult]:
        related: list[NodeSearchResult] = []
        for node_id in related_target_ids:
            try:
                node = self.graph_service.get_node(node_id)
            except Exception:
                trace.append(
                    _trace(
                        "graph_hydration",
                        "Skipped missing related graph target.",
                        status="skipped",
                        target_id=node_id,
                    )
                )
                continue
            related.append(self._canonical_for_node(node, trace=trace) or node)
        return _dedupe_nodes(related)

    def _expanded_neighborhood(
        self,
        hits: list[SemanticMemoryHit],
        *,
        include_archived: bool,
    ) -> NeighborhoodResult:
        nodes: list[NodeSearchResult] = []
        relationships: list[RelationshipResult] = []
        seed_ids = _dedupe(
            [
                hit.canonical_target_id or hit.primary_target_id
                for hit in hits
            ]
            + [related_id for hit in hits for related_id in hit.related_target_ids]
        )
        for seed_id in seed_ids:
            try:
                neighborhood = self.graph_service.get_neighborhood(seed_id, depth=1, limit=30)
            except Exception:
                try:
                    nodes.append(self.graph_service.get_node(seed_id))
                except Exception:
                    pass
                continue
            nodes.extend(
                node
                for node in neighborhood.nodes
                if include_archived or not self.projection.is_hidden_node(node)
            )
            relationships.extend(
                relationship
                for relationship in neighborhood.relationships
                if include_archived or not self.projection.is_hidden_relationship(relationship)
            )
        return NeighborhoodResult(
            nodes=_dedupe_nodes(nodes),
            relationships=_dedupe_relationships(relationships),
        )

    def _context_packages(
        self,
        hits: list[SemanticMemoryHit],
        *,
        limit: int,
        trace: list[SemanticSearchTraceEvent],
    ) -> list[GraphContextPackage]:
        packages: list[GraphContextPackage] = []
        for hit in hits[:limit]:
            target_id = hit.canonical_target_id or hit.primary_target_id
            try:
                packages.append(
                    self.graph_service.get_context_package(
                        target_id,
                        include_history=True,
                        timeline_limit=10,
                        relationship_limit=20,
                    )
                )
            except Exception as exc:
                trace.append(
                    _trace(
                        "context_package",
                        "Could not build context package for hydrated hit.",
                        status="skipped",
                        target_id=target_id,
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                )
        return packages

    def _dedupe_and_rank_hits(
        self,
        hits: list[SemanticMemoryHit],
        *,
        limit: int,
    ) -> list[SemanticMemoryHit]:
        by_target: dict[str, SemanticMemoryHit] = {}
        for hit in hits:
            key = hit.canonical_target_id or hit.primary_target_id
            existing = by_target.get(key)
            if existing is None or hit.score > existing.score:
                by_target[key] = hit
        ranked = sorted(by_target.values(), key=lambda item: item.score, reverse=True)[:limit]
        return [
            hit.model_copy(update={"rank": index})
            for index, hit in enumerate(ranked, start=1)
        ]


def _clean_query(query: str) -> str:
    cleaned = str(query or "").strip()
    if not cleaned:
        raise ValueError("Semantic search query cannot be empty.")
    return cleaned


def _bounded_limit(limit: int) -> int:
    if limit < 1:
        raise ValueError("Limit must be greater than 0.")
    return min(limit, 100)


def _semantic_score(distance: float | None) -> float:
    if distance is None:
        return 0.5
    return 1.0 / (1.0 + max(distance, 0.0))


def _graph_boost(node: NodeSearchResult, *, record: StoredVectorRecord | None) -> float:
    boost = 0.0
    lifecycle = node.properties.get("lifecycle_state")
    if lifecycle in {"active", "confirmed", "inferred", None}:
        boost += 0.05
    if node.properties.get("source_ids") or (record and record.source_ids):
        boost += 0.05
    if node.properties.get("emotional_summary") or node.properties.get("emotion_tags"):
        boost += 0.03
    return boost


def _float_value(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _preview(value: Any, *, max_chars: int = 500) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}..."


def _trace(
    stage: str,
    message: str,
    *,
    status: str = "ok",
    **data: Any,
) -> SemanticSearchTraceEvent:
    return SemanticSearchTraceEvent(
        stage=stage,
        status=status,
        message=message,
        data={key: value for key, value in data.items() if value is not None},
    )


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _dedupe_nodes(nodes: Iterable[NodeSearchResult]) -> list[NodeSearchResult]:
    by_id: dict[str, NodeSearchResult] = {}
    for node in nodes:
        by_id[node.properties["id"]] = node
    return list(by_id.values())


def _dedupe_relationships(
    relationships: Iterable[RelationshipResult],
) -> list[RelationshipResult]:
    by_key: dict[str, RelationshipResult] = {}
    for relationship in relationships:
        relationship_id = relationship.properties.get("id")
        key = str(relationship_id or f"{relationship.type}:{relationship.from_id}:{relationship.to_id}")
        by_key[key] = relationship
    return list(by_key.values())
