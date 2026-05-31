from __future__ import annotations

from typing import Any

from my_digital_brain.graph.base import GraphServiceBase
from my_digital_brain.graph.context_package import GraphContextPackageBuilder
from my_digital_brain.graph.contradiction_service import GraphContradictionService
from my_digital_brain.graph.exceptions import GraphValidationError
from my_digital_brain.graph.memory_service import GraphMemoryService
from my_digital_brain.graph.merge_service import GraphMergeService
from my_digital_brain.graph.models import (
    EntityDetailResult,
    GraphAnalyticsItem,
    GraphAnalyticsSummary,
    GraphContextPackage,
    GraphViewResult,
    MapViewResult,
    NodeSearchResult,
    TimelineResult,
)
from my_digital_brain.graph.projection import GraphProjection
from my_digital_brain.graph.utils import normalize_text
from my_digital_brain.graph.write_service import GraphWriteService


class GraphQueryService(GraphServiceBase):
    def __init__(
        self,
        repository: Any,
        writer: GraphWriteService,
        memory: GraphMemoryService,
        contradictions: GraphContradictionService,
        merges: GraphMergeService,
        projection: GraphProjection,
        context_builder: GraphContextPackageBuilder,
    ) -> None:
        super().__init__(repository)
        self.writer = writer
        self.memory = memory
        self.contradictions = contradictions
        self.merges = merges
        self.projection = projection
        self.context_builder = context_builder

    def get_entity_detail(
        self,
        node_id: str,
        *,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 50,
    ) -> EntityDetailResult:
        target = self.writer.get_node(node_id)
        bounded_limit = self._bounded_limit(limit)
        canonical = self.merges.get_canonical_node(node_id)
        if canonical.properties["id"] == target.properties["id"]:
            canonical = None

        relationships = [
            relationship
            for relationship in self.writer.get_node_relationships(node_id, limit=bounded_limit)
            if include_archived or not self.projection.is_hidden_relationship(relationship)
        ]
        affective = self.memory.get_affective_context(node_id, limit=bounded_limit)
        sources = self.get_source_evidence(node_id, limit=bounded_limit)
        changes = (
            self.memory.get_change_records_for_target(node_id, limit=bounded_limit)
            if include_history
            else []
        )
        contradictions = self.contradictions.query_contradictions(
            target_id=node_id,
            limit=bounded_limit,
        )
        merges = self._dedupe_nodes(
            [
                *self.merges.query_merges(canonical_node_id=node_id, limit=bounded_limit),
                *self.merges.query_merges(merged_node_id=node_id, limit=bounded_limit),
            ]
        )

        return EntityDetailResult(
            target=target,
            canonical=canonical,
            relationships=relationships,
            perceptions=self.projection.filter_visible_nodes(
                affective.perceptions,
                include_archived=include_archived,
                include_history=include_history,
            ),
            relationship_contexts=self.projection.filter_visible_nodes(
                affective.relationship_contexts,
                include_archived=include_archived,
                include_history=include_history,
            ),
            sources=sources,
            changes=changes,
            contradictions=contradictions,
            merges=merges,
        )

    def get_memories_for_node(
        self,
        node_id: str,
        *,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 50,
    ) -> GraphViewResult:
        self.writer.get_node(node_id)
        neighborhood = self.repository.get_related_records(
            node_id,
            depth=2,
            limit=self._bounded_limit(limit),
        )
        return self.projection.to_graph_view_result(
            node_id,
            neighborhood,
            include_history=include_history,
            include_archived=include_archived,
        )

    def get_source_evidence(self, target_id: str, *, limit: int = 50) -> list[NodeSearchResult]:
        self.writer.get_node(target_id)
        records = self.repository.find_sources_for_target(
            target_id,
            limit=self._bounded_limit(limit),
        )
        return [NodeSearchResult.model_validate(record) for record in records]

    def get_timeline_for_node(
        self,
        node_id: str,
        *,
        from_time: str | None = None,
        to_time: str | None = None,
        include_history: bool = False,
        limit: int = 100,
    ) -> TimelineResult:
        seed = self.writer.get_node(node_id)
        from_time = self._validate_time_filter(from_time, "from_time")
        to_time = self._validate_time_filter(to_time, "to_time")
        if from_time and to_time and from_time > to_time:
            raise GraphValidationError("from_time cannot be later than to_time")

        neighborhood = self.repository.get_related_records(
            node_id,
            depth=2,
            limit=self._bounded_limit(limit),
        )
        items = [
            self.projection.to_timeline_item(node)
            for node in neighborhood.nodes
            if self.projection.node_can_be_timeline_item(
                node,
                include_history=include_history,
            )
        ]
        items = [
            item
            for item in items
            if self._time_in_range(item.time_value, from_time=from_time, to_time=to_time)
        ]
        items.sort(key=self.projection.timeline_sort_key)
        return TimelineResult(seed=seed, items=items[: self._bounded_limit(limit)])

    def get_neighborhood_view(
        self,
        *,
        seed_id: str,
        depth: int = 1,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 100,
    ) -> GraphViewResult:
        self.writer.get_node(seed_id)
        if depth < 1 or depth > 3:
            raise GraphValidationError("Neighborhood depth must be between 1 and 3")
        neighborhood = self.repository.get_related_records(
            seed_id,
            depth=depth,
            limit=self._bounded_limit(limit),
        )
        return self.projection.to_graph_view_result(
            seed_id,
            neighborhood,
            include_history=include_history,
            include_archived=include_archived,
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
        bounded_limit = self._bounded_limit(limit)
        from_time = self._validate_time_filter(from_time, "from_time")
        to_time = self._validate_time_filter(to_time, "to_time")
        if from_time and to_time and from_time > to_time:
            raise GraphValidationError("from_time cannot be later than to_time")

        if seed_id:
            self.writer.get_node(seed_id)
            neighborhood = self.repository.get_related_records(
                seed_id,
                depth=2,
                limit=bounded_limit,
            )
        else:
            neighborhood = self.repository.find_map_records(
                city=city,
                country=country,
                limit=bounded_limit,
            )

        city_filter = normalize_text(city) if city else None
        country_filter = normalize_text(country) if country else None
        view = self.projection.to_graph_view_result(
            seed_id or "",
            neighborhood,
            include_history=False,
            include_archived=False,
        )
        places = [
            node
            for node in view.nodes
            if node.label == "Place"
            and self.projection.matches_location_filter(
                node,
                city=city_filter,
                country=country_filter,
            )
        ]
        place_ids = {node.id for node in places}
        events = [
            node
            for node in view.nodes
            if node.label == "Event"
            and (
                not place_ids
                or any(
                    relationship.type == "HAPPENED_AT"
                    and relationship.from_id == node.id
                    and relationship.to_id in place_ids
                    for relationship in view.relationships
                )
            )
        ]
        map_node_ids = {node.id for node in places + events}
        relationships = [
            relationship
            for relationship in view.relationships
            if relationship.from_id in map_node_ids and relationship.to_id in map_node_ids
        ]
        timeline = [
            self.projection.to_timeline_item(node)
            for node in neighborhood.nodes
            if node.properties.get("id") in map_node_ids
        ]
        timeline = [
            item
            for item in timeline
            if self._time_in_range(item.time_value, from_time=from_time, to_time=to_time)
        ]
        timeline.sort(key=self.projection.timeline_sort_key)

        return MapViewResult(
            seed_id=seed_id,
            places=places,
            events=events,
            relationships=relationships,
            timeline=timeline[:bounded_limit],
        )

    def get_context_package(
        self,
        node_id: str,
        *,
        include_history: bool = True,
        timeline_limit: int = 20,
        relationship_limit: int = 50,
    ) -> GraphContextPackage:
        target = self.writer.get_node(node_id)
        timeline_limit = self._bounded_limit(timeline_limit)
        relationship_limit = self._bounded_limit(relationship_limit)
        relationships = [
            relationship
            for relationship in self.writer.get_node_relationships(
                node_id,
                limit=relationship_limit,
            )
            if not self.projection.is_hidden_relationship(relationship)
        ]
        affective = self.memory.get_affective_context(node_id, limit=relationship_limit)
        timeline = self.get_timeline_for_node(
            node_id,
            include_history=include_history,
            limit=timeline_limit,
        )
        evidence = self.get_source_evidence(node_id, limit=relationship_limit)
        contradictions = self.contradictions.query_contradictions(
            target_id=node_id,
            status="detected",
            limit=relationship_limit,
        )
        canonical = self.merges.get_canonical_node(node_id)

        return self.context_builder.build(
            target=target,
            relationships=relationships,
            affective=affective,
            timeline=timeline,
            evidence=evidence,
            contradictions=contradictions,
            canonical=canonical,
            timeline_limit=timeline_limit,
        )

    def get_analytics_summary(
        self,
        *,
        include_archived: bool = False,
        limit: int = 20,
    ) -> GraphAnalyticsSummary:
        bounded_limit = self._bounded_limit(limit)
        top_nodes = [
            GraphAnalyticsItem(
                key=item["node"]["properties"]["id"],
                count=item["count"],
                label=self._analytics_node_label(item),
            )
            for item in self.repository.top_connected_nodes(
                include_archived=include_archived,
                limit=bounded_limit,
            )
        ]
        top_tags = [
            GraphAnalyticsItem(key=item["tag"], count=item["count"])
            for item in self.repository.top_emotion_tags(
                include_archived=include_archived,
                limit=bounded_limit,
            )
        ]
        return GraphAnalyticsSummary(
            node_counts=self.repository.count_nodes_by_label(include_archived=include_archived),
            relationship_counts=self.repository.count_relationships_by_type(),
            top_connected_nodes=top_nodes,
            top_emotion_tags=top_tags,
            unresolved_contradictions=self.repository.count_unresolved_contradictions(),
        )

    def _analytics_node_label(self, item: dict[str, Any]) -> str:
        node = NodeSearchResult.model_validate(item["node"])
        return f"{item['node']['label']}: {self.projection.display_title(node)}"
