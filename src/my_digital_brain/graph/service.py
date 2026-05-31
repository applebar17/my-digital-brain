from __future__ import annotations

from typing import TYPE_CHECKING, Any

from my_digital_brain.graph.context_package import GraphContextPackageBuilder
from my_digital_brain.graph.contradiction_service import GraphContradictionService
from my_digital_brain.graph.memory_service import GraphMemoryService
from my_digital_brain.graph.merge_service import GraphMergeService
from my_digital_brain.graph.models import (
    AffectiveContextResult,
    EntityDetailResult,
    GraphAnalyticsSummary,
    GraphContextPackage,
    GraphViewResult,
    LifecycleTransitionRequest,
    MapViewResult,
    NeighborhoodResult,
    NodeSearchResult,
    RelationshipContextDetailResult,
    RelationshipResult,
    TimelineResult,
)
from my_digital_brain.graph.projection import GraphProjection
from my_digital_brain.graph.query_service import GraphQueryService
from my_digital_brain.graph.repository import GraphRepository
from my_digital_brain.graph.write_service import GraphWriteService

if TYPE_CHECKING:
    from my_digital_brain.storage.graph import GraphClient


class GraphService:
    """Stable graph facade used by API routes and callers.

    The implementation is intentionally composed from narrower services so graph
    writes, memory semantics, merge handling, and read projections can evolve
    without turning this facade into another domain monolith.
    """

    def __init__(self, repository: GraphRepository) -> None:
        self.repository = repository
        self.writer = GraphWriteService(repository)
        self.memory = GraphMemoryService(repository, self.writer)
        self.contradictions = GraphContradictionService(
            repository,
            self.writer,
            self.memory,
        )
        self.merges = GraphMergeService(repository, self.writer, self.memory)
        self.projection = GraphProjection()
        self.context_builder = GraphContextPackageBuilder(repository, self.projection)
        self.queries = GraphQueryService(
            repository,
            self.writer,
            self.memory,
            self.contradictions,
            self.merges,
            self.projection,
            self.context_builder,
        )

    @classmethod
    def from_client(cls, client: GraphClient) -> GraphService:
        return cls(GraphRepository(client))

    def upsert_node(self, label: str, properties: dict[str, Any]) -> NodeSearchResult:
        return self.writer.upsert_node(label, properties)

    def patch_node(self, node_id: str, properties: dict[str, Any]) -> NodeSearchResult:
        return self.writer.patch_node(node_id, properties)

    def get_node(self, node_id: str) -> NodeSearchResult:
        return self.writer.get_node(node_id)

    def search_nodes(
        self,
        *,
        label: str | None = None,
        query: str | None = None,
        lifecycle_state: str | None = None,
        privacy_level: str | None = None,
        trust_level: str | None = None,
        limit: int = 25,
    ) -> list[NodeSearchResult]:
        return self.writer.search_nodes(
            label=label,
            query=query,
            lifecycle_state=lifecycle_state,
            privacy_level=privacy_level,
            trust_level=trust_level,
            limit=limit,
        )

    def upsert_relationship(
        self,
        relationship_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any],
    ) -> RelationshipResult:
        return self.writer.upsert_relationship(relationship_type, from_id, to_id, properties)

    def get_node_relationships(
        self,
        node_id: str,
        *,
        relationship_type: str | None = None,
        direction: str = "both",
        limit: int = 50,
    ) -> list[RelationshipResult]:
        return self.writer.get_node_relationships(
            node_id,
            relationship_type=relationship_type,
            direction=direction,
            limit=limit,
        )

    def get_neighborhood(
        self,
        node_id: str,
        *,
        depth: int = 1,
        limit: int = 50,
    ) -> NeighborhoodResult:
        return self.writer.get_neighborhood(node_id, depth=depth, limit=limit)

    def get_affective_context(self, node_id: str, *, limit: int = 50) -> AffectiveContextResult:
        return self.memory.get_affective_context(node_id, limit=limit)

    def create_relationship_state(
        self,
        context_id: str,
        properties: dict[str, Any],
        *,
        make_current: bool = True,
    ) -> NodeSearchResult:
        return self.memory.create_relationship_state(
            context_id,
            properties,
            make_current=make_current,
        )

    def get_relationship_states(
        self,
        context_id: str,
        *,
        limit: int = 50,
    ) -> list[NodeSearchResult]:
        return self.memory.get_relationship_states(context_id, limit=limit)

    def get_relationship_context_detail(
        self,
        context_id: str,
        *,
        include_state_history: bool = False,
        limit: int = 50,
    ) -> RelationshipContextDetailResult:
        return self.memory.get_relationship_context_detail(
            context_id,
            include_state_history=include_state_history,
            limit=limit,
        )

    def create_change_record(self, properties: dict[str, Any]) -> NodeSearchResult:
        return self.memory.create_change_record(properties)

    def get_change_records_for_target(
        self,
        target_id: str,
        *,
        target_kind: str | None = None,
        limit: int = 50,
    ) -> list[NodeSearchResult]:
        return self.memory.get_change_records_for_target(
            target_id,
            target_kind=target_kind,
            limit=limit,
        )

    def transition_node_lifecycle(
        self,
        node_id: str,
        transition: LifecycleTransitionRequest,
    ) -> NodeSearchResult:
        return self.memory.transition_node_lifecycle(node_id, transition)

    def transition_relationship_lifecycle(
        self,
        relationship_id: str,
        transition: LifecycleTransitionRequest,
    ) -> RelationshipResult:
        return self.memory.transition_relationship_lifecycle(relationship_id, transition)

    def create_contradiction(
        self,
        properties: dict[str, Any],
        *,
        target_ids: list[str] | None = None,
    ) -> NodeSearchResult:
        return self.contradictions.create_contradiction(properties, target_ids=target_ids)

    def query_contradictions(
        self,
        *,
        target_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        contradiction_type: str | None = None,
        limit: int = 50,
    ) -> list[NodeSearchResult]:
        return self.contradictions.query_contradictions(
            target_id=target_id,
            status=status,
            severity=severity,
            contradiction_type=contradiction_type,
            limit=limit,
        )

    def update_contradiction(
        self,
        contradiction_id: str,
        properties: dict[str, Any],
    ) -> NodeSearchResult:
        return self.contradictions.update_contradiction(contradiction_id, properties)

    def create_merge_record(
        self,
        *,
        canonical_node_id: str,
        merged_node_ids: list[str],
        reason: str | None = None,
        performed_by: str = "system",
        source_ids: list[str] | None = None,
        extraction_run_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NodeSearchResult:
        return self.merges.create_merge_record(
            canonical_node_id=canonical_node_id,
            merged_node_ids=merged_node_ids,
            reason=reason,
            performed_by=performed_by,
            source_ids=source_ids,
            extraction_run_ids=extraction_run_ids,
            metadata=metadata,
        )

    def query_merges(
        self,
        *,
        canonical_node_id: str | None = None,
        merged_node_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[NodeSearchResult]:
        return self.merges.query_merges(
            canonical_node_id=canonical_node_id,
            merged_node_id=merged_node_id,
            status=status,
            limit=limit,
        )

    def update_merge_record(self, merge_id: str, properties: dict[str, Any]) -> NodeSearchResult:
        return self.merges.update_merge_record(merge_id, properties)

    def apply_merge(self, merge_id: str) -> NodeSearchResult:
        return self.merges.apply_merge(merge_id)

    def get_canonical_node(self, node_id: str) -> NodeSearchResult:
        return self.merges.get_canonical_node(node_id)

    def get_entity_detail(
        self,
        node_id: str,
        *,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 50,
    ) -> EntityDetailResult:
        return self.queries.get_entity_detail(
            node_id,
            include_history=include_history,
            include_archived=include_archived,
            limit=limit,
        )

    def get_memories_for_node(
        self,
        node_id: str,
        *,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 50,
    ) -> GraphViewResult:
        return self.queries.get_memories_for_node(
            node_id,
            include_history=include_history,
            include_archived=include_archived,
            limit=limit,
        )

    def get_source_evidence(self, target_id: str, *, limit: int = 50) -> list[NodeSearchResult]:
        return self.queries.get_source_evidence(target_id, limit=limit)

    def get_timeline_for_node(
        self,
        node_id: str,
        *,
        from_time: str | None = None,
        to_time: str | None = None,
        include_history: bool = False,
        limit: int = 100,
    ) -> TimelineResult:
        return self.queries.get_timeline_for_node(
            node_id,
            from_time=from_time,
            to_time=to_time,
            include_history=include_history,
            limit=limit,
        )

    def get_neighborhood_view(
        self,
        *,
        seed_id: str,
        depth: int = 1,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 100,
    ) -> GraphViewResult:
        return self.queries.get_neighborhood_view(
            seed_id=seed_id,
            depth=depth,
            include_history=include_history,
            include_archived=include_archived,
            limit=limit,
        )

    def get_map_view(
        self,
        *,
        seed_id: str | None = None,
        city: str | None = None,
        country: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int = 100,
    ) -> MapViewResult:
        return self.queries.get_map_view(
            seed_id=seed_id,
            city=city,
            country=country,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
        )

    def get_context_package(
        self,
        node_id: str,
        *,
        include_history: bool = True,
        timeline_limit: int = 20,
        relationship_limit: int = 50,
    ) -> GraphContextPackage:
        return self.queries.get_context_package(
            node_id,
            include_history=include_history,
            timeline_limit=timeline_limit,
            relationship_limit=relationship_limit,
        )

    def get_analytics_summary(
        self,
        *,
        include_archived: bool = False,
        limit: int = 20,
    ) -> GraphAnalyticsSummary:
        return self.queries.get_analytics_summary(
            include_archived=include_archived,
            limit=limit,
        )
