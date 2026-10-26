"""Adapter from existing graph/RAG services to the target memory-search contract."""

from datetime import UTC, datetime

from my_digital_brain.graph.models import GraphViewNode, GraphViewRelationship, NodeSearchResult
from my_digital_brain.graph.registry import validate_node_label, validate_relationship_type
from my_digital_brain.graph.service import GraphService
from my_digital_brain.rag.search import SemanticMemorySearchService
from product.application.memory_search.models import (
    MemorySearchFiltersDTO,
    MemorySearchNodeDTO,
    MemorySearchRelationshipDTO,
    MemorySearchResultDTO,
    MemorySearchSeedDTO,
)


class ExistingMemorySearchBackend:
    """Reuse current semantic ranking and graph traversal behind the target contract.

    The graph and semantic services supplied here must already be scoped to the
    configured application owner. The explicit owner check prevents composition
    from accidentally reusing that bound backend for another owner.
    """

    def __init__(
        self,
        owner_id: str,
        semantic_search: SemanticMemorySearchService,
        graph_service: GraphService,
    ) -> None:
        self.owner_id = owner_id
        self.semantic_search = semantic_search
        self.graph_service = graph_service

    def semantic_seeds(
        self,
        owner_id: str,
        query: str,
        *,
        filters: MemorySearchFiltersDTO,
        limit: int,
    ) -> list[MemorySearchSeedDTO]:
        """Delegate similarity ranking and retain only canonical requested labels.

        Dependencies:
            `SemanticMemorySearchService` owns embedding, vector retrieval,
            ranking, and hit hydration. This adapter only normalizes its ranked
            hits into the target seed contract.
        """
        self._require_owner(owner_id)
        labels = [validate_node_label(label) for label in filters.node_labels]
        result = self.semantic_search.search_semantic(
            query,
            limit=limit,
            target_ids=filters.seed_backend_ids,
            graph_focus="narrow",
        )

        seeds: list[MemorySearchSeedDTO] = []
        seen: set[str] = set()
        for hit in result.hits:
            backend_id = hit.display_target_id or hit.primary_target_id
            label = hit.display_target_label or hit.primary_target_label
            if labels and label not in labels:
                continue
            if backend_id in seen:
                continue
            seen.add(backend_id)
            seeds.append(
                MemorySearchSeedDTO(
                    backend_id=backend_id,
                    label=label,
                    title=hit.title or f"Unnamed {label}",
                    summary=hit.description or hit.document_preview,
                )
            )
        return seeds[:limit]

    def deterministic_seeds(
        self,
        owner_id: str,
        filters: MemorySearchFiltersDTO,
        *,
        limit: int,
    ) -> list[MemorySearchSeedDTO]:
        """Use existing exact-ID and property search without semantic ranking."""
        self._require_owner(owner_id)
        nodes: list[NodeSearchResult] = []
        for backend_id in filters.seed_backend_ids:
            nodes.append(self.graph_service.get_node(backend_id))

        labels = [validate_node_label(label) for label in filters.node_labels]
        if filters.property_query is not None or labels:
            search_labels: list[str | None] = labels or [None]
            for label in search_labels:
                nodes.extend(
                    self.graph_service.search_nodes(
                        label=label,
                        query=filters.property_query,
                        limit=limit,
                    )
                )

        return self._node_seeds(nodes, limit=limit)

    def hydrate(
        self,
        owner_id: str,
        seed_backend_ids: list[str],
        *,
        filters: MemorySearchFiltersDTO,
        depth: int,
        limit: int,
    ) -> MemorySearchResultDTO:
        """Hydrate bounded existing graph views and apply result refinements.

        Dependencies:
            `GraphService` owns node lookup and one-to-three-degree traversal.
            This adapter merges those views, applies accepted type/time filters,
            and preserves endpoint coherence in the bounded target result.
        """
        self._require_owner(owner_id)
        relationship_types = {
            validate_relationship_type(value) for value in filters.relationship_types
        }
        nodes_by_id: dict[str, MemorySearchNodeDTO] = {}
        relationships_by_id: dict[str, MemorySearchRelationshipDTO] = {}

        for seed_id in seed_backend_ids:
            if depth == 0:
                node = self.graph_service.get_node(seed_id)
                projected = self.graph_service.projection.to_graph_view_node(node)
                nodes_by_id.setdefault(projected.id, self._node(projected))
                continue

            view = self.graph_service.get_neighborhood_view(
                seed_id=seed_id,
                depth=depth,
                limit=limit + 1,
            )
            for node in view.nodes:
                nodes_by_id.setdefault(node.id, self._node(node))
            for relationship in view.relationships:
                relationships_by_id.setdefault(
                    relationship.id,
                    self._relationship(relationship),
                )

        ordered_nodes = self._seed_first_nodes(seed_backend_ids, nodes_by_id)
        time_filtered_nodes = [
            node
            for node in ordered_nodes
            if self._time_allowed(
                node.temporal_summary,
                from_time=filters.from_time,
                to_time=filters.to_time,
            )
        ]
        selected_nodes = time_filtered_nodes[:limit]
        selected_node_ids = {node.backend_id for node in selected_nodes}

        filtered_relationships = [
            relationship
            for relationship in relationships_by_id.values()
            if (not relationship_types or relationship.relationship_type in relationship_types)
            and relationship.from_backend_id in selected_node_ids
            and relationship.to_backend_id in selected_node_ids
            and self._time_allowed(
                relationship.temporal_summary,
                from_time=filters.from_time,
                to_time=filters.to_time,
            )
        ]
        selected_relationships = filtered_relationships[:limit]
        return MemorySearchResultDTO(
            seed_backend_ids=[
                seed_id for seed_id in seed_backend_ids if seed_id in selected_node_ids
            ],
            nodes=selected_nodes,
            relationships=selected_relationships,
            truncated=(len(time_filtered_nodes) > limit or len(filtered_relationships) > limit),
        )

    def _require_owner(self, owner_id: str) -> None:
        if owner_id != self.owner_id:
            raise ValueError("Memory search backend is not scoped to the supplied owner.")

    @staticmethod
    def _node_seeds(nodes: list[NodeSearchResult], *, limit: int) -> list[MemorySearchSeedDTO]:
        seeds: list[MemorySearchSeedDTO] = []
        seen: set[str] = set()
        for node in nodes:
            backend_id = str(node.properties["id"])
            if backend_id in seen:
                continue
            seen.add(backend_id)
            seeds.append(
                MemorySearchSeedDTO(
                    backend_id=backend_id,
                    label=node.label,
                    title=node.presentation.title,
                    summary=node.presentation.summary,
                )
            )
            if len(seeds) >= limit:
                break
        return seeds

    @staticmethod
    def _node(node: GraphViewNode) -> MemorySearchNodeDTO:
        return MemorySearchNodeDTO(
            backend_id=node.id,
            label=node.label,
            title=node.title or f"Unnamed {node.label}",
            summary=node.description,
            temporal_summary=node.temporal_summary,
        )

    @staticmethod
    def _relationship(relationship: GraphViewRelationship) -> MemorySearchRelationshipDTO:
        return MemorySearchRelationshipDTO(
            backend_id=relationship.id,
            relationship_type=relationship.type,
            from_backend_id=relationship.from_id,
            to_backend_id=relationship.to_id,
            summary=relationship.description,
            temporal_summary=relationship.temporal_summary,
        )

    @staticmethod
    def _seed_first_nodes(
        seed_backend_ids: list[str],
        nodes_by_id: dict[str, MemorySearchNodeDTO],
    ) -> list[MemorySearchNodeDTO]:
        ordered_ids = [
            *[seed_id for seed_id in seed_backend_ids if seed_id in nodes_by_id],
            *[node_id for node_id in nodes_by_id if node_id not in seed_backend_ids],
        ]
        return [nodes_by_id[node_id] for node_id in ordered_ids]

    @classmethod
    def _time_allowed(
        cls,
        temporal_summary: str | None,
        *,
        from_time: str | None,
        to_time: str | None,
    ) -> bool:
        if from_time is None and to_time is None:
            return True
        if temporal_summary is None:
            return False
        value = cls._parse_time(temporal_summary.split(" (", maxsplit=1)[0])
        if value is None:
            return False
        lower = cls._parse_time(from_time)
        upper = cls._parse_time(to_time)
        return (lower is None or value >= lower) and (upper is None or value <= upper)

    @staticmethod
    def _parse_time(value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed
