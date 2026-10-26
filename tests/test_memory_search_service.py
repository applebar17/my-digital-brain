from __future__ import annotations

from typing import Any

import pytest

from my_digital_brain.graph.models import (
    GraphViewNode,
    GraphViewRelationship,
    GraphViewResult,
    NodeSearchResult,
)
from my_digital_brain.graph.projection import GraphProjection
from my_digital_brain.rag.memory_search_adapter import ExistingMemorySearchBackend
from my_digital_brain.rag.models import SemanticMemoryHit, SemanticMemorySearchResult
from product.application.memory_search import (
    MemorySearchFiltersDTO,
    MemorySearchNodeDTO,
    MemorySearchRequestDTO,
    MemorySearchResultDTO,
    MemorySearchSeedDTO,
    MemorySearchService,
)


class RecordingMemorySearchBackend:
    """Functional fake recording orchestration across the target backend contract."""

    def __init__(
        self,
        *,
        semantic: list[MemorySearchSeedDTO] | None = None,
        deterministic: list[MemorySearchSeedDTO] | None = None,
    ) -> None:
        self.semantic = semantic or []
        self.deterministic = deterministic or []
        self.calls: list[tuple[str, str]] = []
        self.hydrated_ids: list[str] | None = None

    def semantic_seeds(
        self,
        owner_id: str,
        query: str,
        *,
        filters: MemorySearchFiltersDTO,
        limit: int,
    ) -> list[MemorySearchSeedDTO]:
        self.calls.append(("semantic", owner_id))
        return self.semantic[:limit]

    def deterministic_seeds(
        self,
        owner_id: str,
        filters: MemorySearchFiltersDTO,
        *,
        limit: int,
    ) -> list[MemorySearchSeedDTO]:
        self.calls.append(("deterministic", owner_id))
        return self.deterministic[:limit]

    def hydrate(
        self,
        owner_id: str,
        seed_backend_ids: list[str],
        *,
        filters: MemorySearchFiltersDTO,
        depth: int,
        limit: int,
    ) -> MemorySearchResultDTO:
        self.calls.append(("hydrate", owner_id))
        self.hydrated_ids = seed_backend_ids
        return MemorySearchResultDTO(
            seed_backend_ids=seed_backend_ids,
            nodes=[
                MemorySearchNodeDTO(
                    backend_id=backend_id,
                    label="Person",
                    title=backend_id,
                )
                for backend_id in seed_backend_ids
            ],
        )


def _seed(backend_id: str) -> MemorySearchSeedDTO:
    return MemorySearchSeedDTO(backend_id=backend_id, label="Person", title=backend_id)


def test_memory_search_combines_ranked_seed_sources_once_before_hydration() -> None:
    backend = RecordingMemorySearchBackend(
        semantic=[_seed("node-a"), _seed("node-b")],
        deterministic=[_seed("node-b"), _seed("node-c")],
    )
    service = MemorySearchService(backend)

    result = service.search(
        "owner-1",
        MemorySearchRequestDTO(
            semantic_query="friends from university",
            filters=MemorySearchFiltersDTO(property_query="Marco"),
            neighborhood_depth=2,
            limit=3,
        ),
    )

    assert backend.calls == [
        ("semantic", "owner-1"),
        ("deterministic", "owner-1"),
        ("hydrate", "owner-1"),
    ]
    assert backend.hydrated_ids == ["node-a", "node-b", "node-c"]
    assert result.seed_backend_ids == ["node-a", "node-b", "node-c"]


def test_memory_search_supports_filters_only_and_skips_hydration_for_no_match() -> None:
    matching_backend = RecordingMemorySearchBackend(deterministic=[_seed("node-place")])
    matching = MemorySearchService(matching_backend).search(
        "owner-1",
        MemorySearchRequestDTO(
            filters=MemorySearchFiltersDTO(node_labels=["Place"]),
            neighborhood_depth=0,
        ),
    )
    empty_backend = RecordingMemorySearchBackend()
    empty = MemorySearchService(empty_backend).search(
        "owner-1",
        MemorySearchRequestDTO(semantic_query="not present"),
    )

    assert matching.seed_backend_ids == ["node-place"]
    assert matching_backend.calls == [
        ("deterministic", "owner-1"),
        ("hydrate", "owner-1"),
    ]
    assert empty == MemorySearchResultDTO()
    assert empty_backend.calls == [("semantic", "owner-1")]


class StaticSemanticSearch:
    def search_semantic(self, query: str, **kwargs: Any) -> SemanticMemorySearchResult:
        return self._result(query)

    def search_hybrid(
        self,
        query: str,
        label: str | None = None,
        **kwargs: Any,
    ) -> SemanticMemorySearchResult:
        return self._result(query)

    @staticmethod
    def _result(query: str) -> SemanticMemorySearchResult:
        return SemanticMemorySearchResult(
            query=query,
            hits=[
                SemanticMemoryHit(
                    rank=1,
                    score=0.9,
                    source="semantic",
                    primary_target_id="node-seed",
                    primary_target_label="Person",
                    display_target_id="node-seed",
                    display_target_label="Person",
                    title="Marco",
                )
            ],
            graph_view=GraphViewResult(seed_id="node-seed", nodes=[], relationships=[]),
        )


class StaticGraphSearch:
    projection = GraphProjection()

    def get_node(self, node_id: str) -> NodeSearchResult:
        return NodeSearchResult(
            label="Person",
            labels=["Person"],
            properties={"id": node_id, "display_name": "Marco"},
        )

    def search_nodes(self, **kwargs: Any) -> list[NodeSearchResult]:
        return []

    def get_neighborhood_view(self, **kwargs: Any) -> GraphViewResult:
        return GraphViewResult(
            seed_id="node-seed",
            nodes=[
                GraphViewNode(
                    id="node-seed",
                    label="Person",
                    title="Marco",
                    temporal_summary="2026-01-10 (happened_at)",
                ),
                GraphViewNode(
                    id="node-old",
                    label="Event",
                    title="Old event",
                    temporal_summary="2025-01-10 (happened_at)",
                ),
                GraphViewNode(
                    id="node-current",
                    label="Event",
                    title="Current event",
                    temporal_summary="2026-02-10 (happened_at)",
                ),
                GraphViewNode(
                    id="node-extra",
                    label="Place",
                    title="Current place",
                    temporal_summary="2026-03-10 (happened_at)",
                ),
            ],
            relationships=[
                GraphViewRelationship(
                    id="rel-keep",
                    type="KNOWS",
                    from_id="node-seed",
                    to_id="node-current",
                    temporal_summary="2026-02-10 (happened_at)",
                ),
                GraphViewRelationship(
                    id="rel-drop",
                    type="RELATED_TO",
                    from_id="node-seed",
                    to_id="node-current",
                ),
            ],
        )


def test_existing_backend_reuses_current_services_with_owner_and_bounded_filters() -> None:
    backend = ExistingMemorySearchBackend(
        "owner-1",
        StaticSemanticSearch(),  # type: ignore[arg-type]
        StaticGraphSearch(),  # type: ignore[arg-type]
    )
    service = MemorySearchService(backend)
    result = service.search(
        "owner-1",
        MemorySearchRequestDTO(
            semantic_query="What happened with Marco?",
            filters=MemorySearchFiltersDTO(
                relationship_types=["KNOWS"],
                from_time="2026-01-01",
            ),
            neighborhood_depth=1,
            limit=2,
        ),
    )

    assert [node.backend_id for node in result.nodes] == ["node-seed", "node-current"]
    assert [relationship.backend_id for relationship in result.relationships] == ["rel-keep"]
    assert result.seed_backend_ids == ["node-seed"]
    assert result.truncated is True
    with pytest.raises(ValueError, match="not scoped"):
        service.search("owner-2", MemorySearchRequestDTO(semantic_query="Marco"))
