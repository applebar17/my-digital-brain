from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
import logging
from typing import Any, Literal

from my_digital_brain.ai.logging import log_event
from my_digital_brain.ai.protocols import EmbeddingProvider, ModelRouter
from my_digital_brain.ai.router import EMBEDDING_TASK, StaticModelRouter
from my_digital_brain.ai.schemas import AIRequestContext, EmbeddingRequest
from my_digital_brain.ai.tracing import traceable
from my_digital_brain.graph.models import (
    GraphContextPackage,
    NeighborhoodResult,
    NodeSearchResult,
    RelationshipResult,
)
from my_digital_brain.graph.projection import GraphProjection
from my_digital_brain.ingestion.contracts import (
    MultiScopeVectorConfig,
    V1_VECTOR_DIMENSIONS,
    VectorScopeName,
    default_v1_vector_scope_config,
)
from my_digital_brain.rag.graph_focus import GraphFocusMode, SearchGraphFocusSelector
from my_digital_brain.rag.models import (
    SemanticMemoryHit,
    SemanticMemorySearchResult,
    SemanticSearchTraceEvent,
    StoredVectorRecord,
    VECTOR_STORE_CHROMA,
)
from my_digital_brain.rag.vector_records import VectorRecordStore
from my_digital_brain.storage.vector import VectorStore

logger = logging.getLogger(__name__)

HIDDEN_VECTOR_STATES = {"archived", "deleted", "expired"}
CONTEXT_LABELS = {
    "Claim",
    "Perception",
    "RelationshipContext",
    "RelationshipState",
    "ProfileMemory",
}
NON_DISPLAY_LABELS = CONTEXT_LABELS | {"MemoryLog", "Source", "MediaAsset"}


@dataclass
class _HydratedVectorHit:
    record: StoredVectorRecord
    scope: VectorScopeName
    scope_weight: float
    distance: float | None
    raw_score: float
    normalized_score: float
    document_preview: str | None
    matched: NodeSearchResult
    matched_canonical: NodeSearchResult | None = None
    display: NodeSearchResult | None = None
    display_canonical: NodeSearchResult | None = None
    related: list[NodeSearchResult] = field(default_factory=list)
    hydration_path: list[str] = field(default_factory=list)

    @property
    def matched_id(self) -> str:
        return str(self.matched.properties["id"])

    @property
    def display_id(self) -> str:
        target = self.display_canonical or self.display or self.matched_canonical or self.matched
        return str(target.properties["id"])

    @property
    def display_target(self) -> NodeSearchResult:
        return self.display_canonical or self.display or self.matched_canonical or self.matched


class SemanticMemorySearchService:
    """Scoped graph-grounded retrieval over Wave 2 vector scopes."""

    def __init__(
        self,
        *,
        graph_service: Any,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        vector_record_store: VectorRecordStore,
        model_router: ModelRouter | None = None,
        projection: GraphProjection | None = None,
        graph_focus_selector: SearchGraphFocusSelector | None = None,
        vector_config: MultiScopeVectorConfig | None = None,
        vector_store_name: str = VECTOR_STORE_CHROMA,
        owner_graph_node_id: str | None = None,
    ) -> None:
        self.graph_service = graph_service
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.vector_record_store = vector_record_store
        self.model_router = model_router or StaticModelRouter()
        self.projection = projection or GraphProjection()
        self.graph_focus_selector = graph_focus_selector or SearchGraphFocusSelector()
        self.vector_config = vector_config or default_v1_vector_scope_config()
        self.vector_store_name = vector_store_name
        self.owner_graph_node_id = owner_graph_node_id

    @traceable(name="Graph RAG Scoped Semantic Search", run_type="retriever")
    def search_semantic(
        self,
        query: str,
        *,
        limit: int = 10,
        include_archived: bool = False,
        include_history: bool = False,
        graph_focus: GraphFocusMode = "broad",
        target_ids: list[str] | None = None,
    ) -> SemanticMemorySearchResult:
        return self._search(
            query,
            mode="semantic",
            limit=limit,
            include_archived=include_archived,
            include_history=include_history,
            graph_focus=graph_focus,
            target_ids=target_ids or [],
        )

    @traceable(name="Graph RAG Scoped Hybrid Search", run_type="retriever")
    def search_hybrid(
        self,
        query: str,
        *,
        label: str | None = None,
        limit: int = 10,
        include_archived: bool = False,
        include_history: bool = False,
        graph_focus: GraphFocusMode = "broad",
        target_ids: list[str] | None = None,
    ) -> SemanticMemorySearchResult:
        return self._search(
            query,
            mode="hybrid",
            label=label,
            limit=limit,
            include_archived=include_archived,
            include_history=include_history,
            graph_focus=graph_focus,
            target_ids=target_ids or [],
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
        graph_focus: GraphFocusMode,
        target_ids: list[str],
    ) -> SemanticMemorySearchResult:
        query = _clean_query(query)
        limit = _bounded_limit(limit)
        trace: list[SemanticSearchTraceEvent] = []
        allowed_ids = self._expanded_allowed_ids(target_ids, trace=trace)

        vector_hits = self._scoped_vector_hits(
            query,
            limit=limit,
            include_archived=include_archived,
            trace=trace,
        )
        if allowed_ids:
            before = len(vector_hits)
            vector_hits = [
                hit for hit in vector_hits if self._hit_intersects_allowed(hit, allowed_ids)
            ]
            trace.append(
                _trace(
                    "target_filter",
                    "Filtered scoped vector hits against requested graph target context.",
                    requested_target_ids=target_ids,
                    allowed_target_count=len(allowed_ids),
                    before_count=before,
                    after_count=len(vector_hits),
                )
            )

        hits = self._merge_hydrated_hits(vector_hits, limit=limit)
        if mode == "hybrid":
            property_hits = self._property_hits(
                query,
                label=label,
                include_archived=include_archived,
                allowed_ids=allowed_ids,
                limit=limit,
                trace=trace,
            )
            hits = self._dedupe_and_rank_hits([*hits, *property_hits], limit=limit)

        focus = self.graph_focus_selector.select(hits, mode=graph_focus)
        neighborhood = self._expanded_neighborhood(
            list(focus.selected_hits),
            include_archived=include_archived,
            expand_related_targets=graph_focus == "broad",
        )
        graph_seed_id = focus.selected_target_ids[0] if focus.selected_target_ids else ""
        graph_view = self.projection.to_graph_view_result(
            seed_id=graph_seed_id,
            neighborhood=neighborhood,
            include_history=include_history,
            include_archived=include_archived,
        )
        context_packages = self._context_packages(hits, limit=min(limit, 5), trace=trace)
        trace.append(
            _trace(
                "graph_assembly",
                "Rendered graph assembled from folded display targets.",
                focus_mode=focus.mode,
                focus_algorithm=focus.algorithm,
                focus_reason=focus.reason,
                focus_threshold=focus.threshold,
                selected_hit_count=len(focus.selected_hits),
                excluded_hit_count=len(focus.excluded_hits),
                selected_target_ids=focus.selected_target_ids,
                excluded_target_ids=focus.excluded_target_ids,
                graph_seed_id=graph_view.seed_id,
                graph_node_ids=[node.id for node in graph_view.nodes],
                graph_relationship_ids=[
                    relationship.id for relationship in graph_view.relationships
                ],
            )
        )
        trace.append(
            _trace(
                "ranking",
                "Ranked scoped hydrated graph-grounded hits.",
                hit_count=len(hits),
                graph_node_count=len(graph_view.nodes),
                graph_relationship_count=len(graph_view.relationships),
                context_package_count=len(context_packages),
            )
        )
        log_event(
            logger,
            "rag.scoped_search.done",
            component="rag",
            mode=mode,
            hit_count=len(hits),
            graph_node_count=len(graph_view.nodes),
            graph_relationship_count=len(graph_view.relationships),
        )
        return SemanticMemorySearchResult(
            query=query,
            mode=mode,
            collection="scoped",
            hits=hits,
            graph_view=graph_view,
            context_packages=context_packages,
            trace=trace,
        )

    def _scoped_vector_hits(
        self,
        query: str,
        *,
        limit: int,
        include_archived: bool,
        trace: list[SemanticSearchTraceEvent],
    ) -> list[_HydratedVectorHit]:
        route = self.model_router.route(
            EMBEDDING_TASK,
            AIRequestContext(purpose="semantic_memory_search"),
        )
        embedding_result = self.embedding_provider.embed(
            EmbeddingRequest(
                texts=[query],
                model=route.model,
                dimensions=V1_VECTOR_DIMENSIONS,
                context=AIRequestContext(purpose="semantic_memory_search"),
                metadata={"route": route.model_dump(mode="json", exclude_none=True)},
            )
        )
        query_embedding = embedding_result.embeddings[0]
        trace.append(
            _trace(
                "query_embedding",
                "Embedded query once for all scoped vector collections.",
                model=route.model,
                provider=route.provider,
                dimension_count=len(query_embedding),
            )
        )

        hits: list[_HydratedVectorHit] = []
        for scope in self.vector_config.scopes:
            if not scope.enabled:
                continue
            raw_hits = self.vector_store.search(
                scope.collection,
                query_embedding,
                limit=max(limit * 3, limit),
            )
            trace.append(
                _trace(
                    "vector_search",
                    "Vector store returned scoped semantic candidates.",
                    scope=scope.scope,
                    collection=scope.collection,
                    raw_hit_count=len(raw_hits),
                )
            )
            for raw in raw_hits:
                hit = self._hydrate_raw_hit(
                    raw,
                    scope_name=scope.scope,
                    collection=scope.collection,
                    scope_weight=scope.ranking_weight,
                    include_archived=include_archived,
                    trace=trace,
                )
                if hit is not None:
                    hits.append(hit)
        return hits

    def _hydrate_raw_hit(
        self,
        raw: dict[str, Any],
        *,
        scope_name: VectorScopeName,
        collection: str,
        scope_weight: float,
        include_archived: bool,
        trace: list[SemanticSearchTraceEvent],
    ) -> _HydratedVectorHit | None:
        vector_id = str(raw.get("id") or "")
        if not vector_id:
            return None
        record = self.vector_record_store.get_by_vector_id(
            vector_id,
            vector_store=self.vector_store_name,
            collection=collection,
        )
        if record is None:
            trace.append(
                _trace(
                    "vector_record",
                    "Skipped Chroma hit without relational vector record.",
                    status="skipped",
                    vector_id=vector_id,
                    collection=collection,
                )
            )
            return None
        if not include_archived and record.lifecycle_state in HIDDEN_VECTOR_STATES:
            trace.append(
                _trace(
                    "vector_record",
                    "Skipped hidden vector record.",
                    status="skipped",
                    vector_id=vector_id,
                    collection=collection,
                    lifecycle_state=record.lifecycle_state,
                )
            )
            return None

        matched = self._get_node(record.primary_target_id, trace=trace, role="matched")
        if matched is None:
            return None
        matched_canonical = self._canonical_for_node(matched, trace=trace)
        related = self._hydrate_related(record.related_target_ids, trace=trace)
        if matched.label == "ProfileMemory" and not _profile_hit_allowed(
            matched, related, owner_graph_node_id=self.owner_graph_node_id
        ):
            return None
        display = self._display_target_for_hit(record, matched, related, trace=trace)
        display_canonical = self._canonical_for_node(display, trace=trace) if display else None
        display_target = display_canonical or display or matched_canonical or matched
        if not include_archived and self.projection.is_hidden_node(display_target):
            return None

        distance = _float_value(raw.get("distance"))
        raw_score = _semantic_score(distance)
        normalized_score = raw_score * scope_weight
        return _HydratedVectorHit(
            record=record,
            scope=scope_name,
            scope_weight=scope_weight,
            distance=distance,
            raw_score=raw_score,
            normalized_score=normalized_score,
            document_preview=_preview(raw.get("document")),
            matched=matched,
            matched_canonical=matched_canonical,
            display=display,
            display_canonical=display_canonical,
            related=related,
            hydration_path=_dedupe(
                [
                    f"scope:{scope_name}",
                    f"matched:{matched.label}",
                    f"display:{display_target.label}",
                ]
            ),
        )

    def _display_target_for_hit(
        self,
        record: StoredVectorRecord,
        matched: NodeSearchResult,
        related: list[NodeSearchResult],
        *,
        trace: list[SemanticSearchTraceEvent],
    ) -> NodeSearchResult:
        if record.hit_role == "domain_node":
            return matched
        if record.hit_role == "memory_log":
            target_id = record.canonical_target_id or _text_value(
                matched.properties.get("primary_host_target_id")
            )
            target = self._get_node(target_id, trace=trace, role="memory_log_host") if target_id else None
            if target is not None:
                return target
        target = _first_displayable_related(related)
        if target is not None:
            return target
        return matched

    def _merge_hydrated_hits(
        self,
        hydrated_hits: list[_HydratedVectorHit],
        *,
        limit: int,
    ) -> list[SemanticMemoryHit]:
        grouped: dict[str, list[_HydratedVectorHit]] = {}
        for hit in hydrated_hits:
            grouped.setdefault(hit.display_id, []).append(hit)

        merged: list[SemanticMemoryHit] = []
        for display_id, group in grouped.items():
            group = sorted(group, key=lambda item: item.normalized_score, reverse=True)
            best = group[0]
            display = best.display_target
            matched_records = [_matched_record_summary(item) for item in group]
            related_ids = _dedupe(
                related_id
                for item in group
                for related_id in [
                    *item.record.related_target_ids,
                    *[str(node.properties["id"]) for node in item.related],
                    item.matched_id,
                ]
                if related_id != display_id
            )
            hit = SemanticMemoryHit(
                rank=0,
                score=round(best.normalized_score, 6),
                source="semantic",
                vector_id=best.record.vector_id,
                distance=best.distance,
                collection=best.record.collection,
                scope=best.scope,
                hit_role=best.record.hit_role,
                embedding_scope=best.record.embedding_scope,
                matched_target_id=best.matched_id,
                matched_target_label=best.matched.label,
                matched_target=self.projection.to_graph_view_node(best.matched),
                display_target_id=display_id,
                display_target_label=display.label,
                primary_target_id=display_id,
                primary_target_label=display.label,
                canonical_target_id=(
                    best.display_canonical.properties["id"]
                    if best.display_canonical
                    else None
                ),
                related_target_ids=related_ids,
                source_ids=_dedupe(
                    source_id for item in group for source_id in item.record.source_ids
                ),
                relationship_ids=_dedupe(
                    rel_id for item in group for rel_id in item.record.relationship_ids
                ),
                raw_score=round(best.raw_score, 6),
                normalized_score=round(best.normalized_score, 6),
                scope_weight=best.scope_weight,
                hydration_path=best.hydration_path,
                matched_records=matched_records,
                title=self.projection.display_title(display),
                description=self.projection.display_description(display),
                document_preview=best.document_preview,
                target=self.projection.to_graph_view_node(display),
                canonical_target=(
                    self.projection.to_graph_view_node(best.display_canonical)
                    if best.display_canonical is not None
                    else None
                ),
                debug={
                    "scope": best.scope,
                    "hit_role": best.record.hit_role,
                    "matched_count": len(group),
                    "matched_target_ids": [item.matched_id for item in group],
                    "raw_score": round(best.raw_score, 6),
                    "normalized_score": round(best.normalized_score, 6),
                    "scope_weight": best.scope_weight,
                    "record_lifecycle_state": best.record.lifecycle_state,
                },
            )
            merged.append(hit)

        ranked = sorted(merged, key=lambda item: item.score, reverse=True)[:limit]
        return [
            hit.model_copy(update={"rank": index})
            for index, hit in enumerate(ranked, start=1)
        ]

    def _property_hits(
        self,
        query: str,
        *,
        label: str | None,
        include_archived: bool,
        allowed_ids: set[str],
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
            if node.label == "ProfileMemory" and not _profile_hit_allowed(
                node,
                self._profile_related_nodes(node, trace=trace),
                owner_graph_node_id=self.owner_graph_node_id,
            ):
                continue
            canonical = self._canonical_for_node(node, trace=trace)
            target = canonical or node
            target_id = str(target.properties["id"])
            if allowed_ids and target_id not in allowed_ids:
                continue
            if not include_archived and self.projection.is_hidden_node(target):
                continue
            hits.append(
                SemanticMemoryHit(
                    rank=0,
                    score=0.7,
                    source="property",
                    hit_role="domain_node",
                    matched_target_id=str(node.properties["id"]),
                    matched_target_label=node.label,
                    matched_target=self.projection.to_graph_view_node(node),
                    display_target_id=target_id,
                    display_target_label=target.label,
                    primary_target_id=str(node.properties["id"]),
                    primary_target_label=node.label,
                    canonical_target_id=(
                        target_id if target_id != node.properties["id"] else None
                    ),
                    related_target_ids=[],
                    source_ids=list(node.properties.get("source_ids", [])),
                    raw_score=0.7,
                    normalized_score=0.7,
                    scope_weight=1.0,
                    hydration_path=["property_search"],
                    matched_records=[_node_summary(node, self.projection, source="property")],
                    title=self.projection.display_title(target),
                    description=self.projection.display_description(target),
                    target=self.projection.to_graph_view_node(node),
                    canonical_target=(
                        self.projection.to_graph_view_node(target)
                        if target_id != node.properties["id"]
                        else None
                    ),
                    debug={"property_match": True},
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

    def _expanded_allowed_ids(
        self,
        target_ids: list[str],
        *,
        trace: list[SemanticSearchTraceEvent],
    ) -> set[str]:
        allowed: set[str] = set()
        for target_id in target_ids:
            node = self._get_node(target_id, trace=trace, role="target_constraint")
            if node is None:
                continue
            allowed.add(str(node.properties["id"]))
            canonical = self._canonical_for_node(node, trace=trace)
            if canonical is not None:
                allowed.add(str(canonical.properties["id"]))
            try:
                neighborhood = self.graph_service.get_neighborhood(target_id, depth=2, limit=100)
            except Exception:
                continue
            allowed.update(str(item.properties["id"]) for item in neighborhood.nodes)
        if allowed:
            trace.append(
                _trace(
                    "target_expansion",
                    "Expanded requested graph target ids into an allowed context set.",
                    requested_target_ids=target_ids,
                    allowed_target_count=len(allowed),
                )
            )
        return allowed

    def _hit_intersects_allowed(self, hit: _HydratedVectorHit, allowed_ids: set[str]) -> bool:
        ids = {
            hit.matched_id,
            hit.display_id,
            *hit.record.related_target_ids,
            *[str(node.properties["id"]) for node in hit.related],
        }
        if hit.matched_canonical is not None:
            ids.add(str(hit.matched_canonical.properties["id"]))
        if hit.display_canonical is not None:
            ids.add(str(hit.display_canonical.properties["id"]))
        return bool(ids & allowed_ids)

    def _get_node(
        self,
        node_id: str | None,
        *,
        trace: list[SemanticSearchTraceEvent],
        role: str,
    ) -> NodeSearchResult | None:
        if not node_id:
            return None
        try:
            return self.graph_service.get_node(node_id)
        except Exception as exc:
            trace.append(
                _trace(
                    "graph_hydration",
                    "Could not hydrate graph target.",
                    status="skipped",
                    target_id=node_id,
                    hydration_role=role,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            )
            return None

    def _canonical_for_node(
        self,
        node: NodeSearchResult,
        *,
        trace: list[SemanticSearchTraceEvent],
    ) -> NodeSearchResult | None:
        if not hasattr(self.graph_service, "get_canonical_node"):
            return None
        node_id = str(node.properties["id"])
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
        return None

    def _hydrate_related(
        self,
        related_target_ids: list[str],
        *,
        trace: list[SemanticSearchTraceEvent],
    ) -> list[NodeSearchResult]:
        related: list[NodeSearchResult] = []
        for node_id in related_target_ids:
            node = self._get_node(node_id, trace=trace, role="related")
            if node is None:
                continue
            related.append(self._canonical_for_node(node, trace=trace) or node)
        return _dedupe_nodes(related)

    def _profile_related_nodes(
        self,
        node: NodeSearchResult,
        *,
        trace: list[SemanticSearchTraceEvent],
    ) -> list[NodeSearchResult]:
        try:
            relationships = self.graph_service.get_node_relationships(
                str(node.properties.get("id", "")), limit=20
            )
        except Exception:
            return []
        ids = [
            relationship.to_id
            if relationship.from_id == node.properties.get("id")
            else relationship.from_id
            for relationship in relationships
            if relationship.type == "DESCRIBES_USER"
        ]
        return self._hydrate_related(ids, trace=trace)

    def _expanded_neighborhood(
        self,
        hits: list[SemanticMemoryHit],
        *,
        include_archived: bool,
        expand_related_targets: bool = True,
    ) -> NeighborhoodResult:
        nodes: list[NodeSearchResult] = []
        relationships: list[RelationshipResult] = []
        primary_seed_ids = [
            hit.display_target_id or hit.canonical_target_id or hit.primary_target_id
            for hit in hits
        ]
        display_seed_id_set = set(primary_seed_ids)
        related_seed_ids = [related_id for hit in hits for related_id in hit.related_target_ids]
        seed_ids = _dedupe(
            primary_seed_ids + (related_seed_ids if expand_related_targets else [])
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
                if (
                    node.label not in NON_DISPLAY_LABELS
                    or str(node.properties.get("id")) in display_seed_id_set
                )
                and (include_archived or not self.projection.is_hidden_node(node))
            )
            relationships.extend(
                relationship
                for relationship in neighborhood.relationships
                if include_archived or not self.projection.is_hidden_relationship(relationship)
            )
            if not any(node.properties.get("id") == seed_id for node in neighborhood.nodes):
                try:
                    seed_node = self.graph_service.get_node(seed_id)
                except Exception:
                    continue
                if (
                    (
                        seed_node.label not in NON_DISPLAY_LABELS
                        or str(seed_node.properties.get("id")) in display_seed_id_set
                    )
                    and (include_archived or not self.projection.is_hidden_node(seed_node))
                ):
                    nodes.append(seed_node)
        visible_node_ids = {node.properties["id"] for node in nodes}
        relationships = [
            relationship
            for relationship in relationships
            if relationship.from_id in visible_node_ids and relationship.to_id in visible_node_ids
        ]
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
            target_id = hit.display_target_id or hit.canonical_target_id or hit.primary_target_id
            try:
                package = self.graph_service.get_context_package(
                    target_id,
                    include_history=True,
                    timeline_limit=10,
                    relationship_limit=20,
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
                continue
            packages.append(
                package.model_copy(
                    update={
                        "matched_records": [
                            *package.matched_records,
                            *hit.matched_records,
                        ]
                    },
                    deep=True,
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
            key = hit.display_target_id or hit.canonical_target_id or hit.primary_target_id
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


def _matched_record_summary(hit: _HydratedVectorHit) -> dict[str, Any]:
    summary = _node_summary(hit.matched, GraphProjection(), source="semantic")
    summary.update(
        {
            "scope": hit.scope,
            "hit_role": hit.record.hit_role,
            "embedding_scope": hit.record.embedding_scope,
            "collection": hit.record.collection,
            "score": round(hit.normalized_score, 6),
            "raw_score": round(hit.raw_score, 6),
            "scope_weight": hit.scope_weight,
        }
    )
    if hit.document_preview:
        summary["document_preview"] = hit.document_preview
    return summary


def _node_summary(
    node: NodeSearchResult,
    projection: GraphProjection,
    *,
    source: str,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "source": source,
        "label": node.label,
        "title": projection.display_title(node),
    }
    description = projection.display_description(node)
    if description:
        summary["description"] = description
    for field in (
        "emotional_summary",
        "original_user_words",
        "status",
        "closeness",
        "relationship_type",
        "source_kind",
        "log_kind",
        "importance",
    ):
        value = node.properties.get(field)
        if value not in (None, "", []):
            summary[field] = value
    temporal = projection.temporal_summary(node.properties)
    if temporal:
        summary["time"] = temporal
    source_ids = node.properties.get("source_ids")
    if source_ids:
        summary["source_ids"] = source_ids
    return summary


def _first_displayable_related(nodes: list[NodeSearchResult]) -> NodeSearchResult | None:
    for node in nodes:
        if node.label not in NON_DISPLAY_LABELS:
            return node
    return nodes[0] if nodes else None


def _profile_hit_allowed(
    node: NodeSearchResult,
    related_nodes: Iterable[NodeSearchResult],
    *,
    owner_graph_node_id: str | None,
) -> bool:
    if not owner_graph_node_id:
        return False
    properties = node.properties
    metadata = properties.get("metadata") or {}
    if (
        properties.get("lifecycle_state", "active") != "active"
        or properties.get("visibility") != "prompt_allowed"
        or properties.get("stability") not in {"stable", "user_confirmed"}
        or metadata.get("requires_confirmation") is True
    ):
        return False
    return any(
        related.label == "Person"
        and str(related.properties.get("id")) == owner_graph_node_id
        and related.properties.get("is_owner") is True
        for related in related_nodes
    )


def _text_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


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
        by_id[str(node.properties["id"])] = node
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
