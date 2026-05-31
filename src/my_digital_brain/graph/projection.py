from __future__ import annotations

from datetime import datetime
from typing import Any

from my_digital_brain.graph.constants import (
    DISPLAY_METADATA_FIELDS,
    HIDDEN_LIFECYCLE_STATES,
    HISTORY_LABELS,
    TIMELINE_TIME_FIELDS,
)
from my_digital_brain.graph.models import (
    GraphViewNode,
    GraphViewRelationship,
    GraphViewResult,
    NeighborhoodResult,
    NodeSearchResult,
    RelationshipResult,
    TimelineItem,
)
from my_digital_brain.graph.utils import normalize_text


class GraphProjection:
    def to_graph_view_result(
        self,
        seed_id: str,
        neighborhood: NeighborhoodResult,
        *,
        include_history: bool,
        include_archived: bool,
    ) -> GraphViewResult:
        visible_nodes = self.filter_visible_nodes(
            neighborhood.nodes,
            include_archived=include_archived,
            include_history=include_history,
        )
        visible_ids = {node.properties["id"] for node in visible_nodes}
        visible_relationships = [
            relationship
            for relationship in neighborhood.relationships
            if relationship.from_id in visible_ids
            and relationship.to_id in visible_ids
            and (include_archived or not self.is_hidden_relationship(relationship))
        ]
        return GraphViewResult(
            seed_id=seed_id,
            nodes=[self.to_graph_view_node(node) for node in visible_nodes],
            relationships=[
                self.to_graph_view_relationship(relationship)
                for relationship in visible_relationships
            ],
        )

    def filter_visible_nodes(
        self,
        nodes: list[NodeSearchResult],
        *,
        include_archived: bool,
        include_history: bool,
    ) -> list[NodeSearchResult]:
        return [
            node
            for node in nodes
            if (include_history or node.label not in HISTORY_LABELS)
            and (include_archived or not self.is_hidden_node(node))
        ]

    def is_hidden_node(self, node: NodeSearchResult) -> bool:
        lifecycle_state = node.properties.get("lifecycle_state")
        return lifecycle_state in HIDDEN_LIFECYCLE_STATES or bool(
            node.properties.get("merged_into_id")
        )

    def is_hidden_relationship(self, relationship: RelationshipResult) -> bool:
        return relationship.properties.get("lifecycle_state") in HIDDEN_LIFECYCLE_STATES

    def to_graph_view_node(self, node: NodeSearchResult) -> GraphViewNode:
        properties = node.properties
        return GraphViewNode(
            id=properties["id"],
            label=node.label,
            title=self.display_title(node),
            description=self.display_description(node),
            lifecycle_state=properties.get("lifecycle_state"),
            privacy_level=properties.get("privacy_level"),
            trust_level=properties.get("trust_level"),
            emotional_summary=properties.get("emotional_summary"),
            temporal_summary=self.temporal_summary(properties),
            latitude=properties.get("latitude"),
            longitude=properties.get("longitude"),
            display_metadata=self.display_metadata(properties),
        )

    def to_graph_view_relationship(
        self,
        relationship: RelationshipResult,
    ) -> GraphViewRelationship:
        properties = relationship.properties
        return GraphViewRelationship(
            id=properties["id"],
            type=relationship.type,
            from_id=relationship.from_id,
            to_id=relationship.to_id,
            description=properties.get("description"),
            lifecycle_state=properties.get("lifecycle_state"),
            emotional_summary=properties.get("emotional_summary"),
            temporal_summary=self.temporal_summary(properties),
        )

    def to_timeline_item(self, node: NodeSearchResult) -> TimelineItem:
        properties = node.properties
        time_value, time_basis = self.timeline_time(properties)
        return TimelineItem(
            id=properties["id"],
            label=node.label,
            title=self.display_title(node),
            description=self.display_description(node),
            time_value=time_value,
            time_basis=properties.get("time_basis") or time_basis,
            time_precision=properties.get("time_precision"),
            source_ids=list(properties.get("source_ids", [])),
            emotional_summary=properties.get("emotional_summary"),
            original_user_words=properties.get("original_user_words"),
        )

    def node_can_be_timeline_item(
        self,
        node: NodeSearchResult,
        *,
        include_history: bool,
    ) -> bool:
        if self.is_hidden_node(node):
            return False
        if not include_history and node.label in HISTORY_LABELS:
            return False
        return self.timeline_time(node.properties)[0] is not None

    def timeline_sort_key(self, item: TimelineItem) -> tuple[int, str]:
        if item.time_value is None:
            return (1, "")
        return (0, item.time_value)

    def timeline_time(self, properties: dict[str, Any]) -> tuple[str | None, str | None]:
        for field in TIMELINE_TIME_FIELDS:
            value = self.stringify_time(properties.get(field))
            if value:
                return value, field
        return None, None

    def temporal_summary(self, properties: dict[str, Any]) -> str | None:
        time_value, basis = self.timeline_time(properties)
        if not time_value:
            return None
        precision = properties.get("time_precision")
        if precision:
            return f"{time_value} ({basis}, {precision})"
        if basis:
            return f"{time_value} ({basis})"
        return time_value

    def display_title(self, node: NodeSearchResult) -> str:
        properties = node.properties
        for field in (
            "display_name",
            "name",
            "title",
            "text",
            "profile_key",
            "value",
            "external_id",
            "description",
        ):
            value = properties.get(field)
            if isinstance(value, str) and value.strip():
                return value
        return f"{node.label} {properties['id']}"

    def display_description(self, node: NodeSearchResult) -> str | None:
        for field in ("description", "emotional_summary", "original_user_words", "text"):
            value = node.properties.get(field)
            if isinstance(value, str) and value.strip():
                return value
        return None

    def display_metadata(self, properties: dict[str, Any]) -> dict[str, Any]:
        return {
            field: properties[field]
            for field in DISPLAY_METADATA_FIELDS
            if properties.get(field) not in (None, "", [])
        }

    def matches_location_filter(
        self,
        node: GraphViewNode,
        *,
        city: str | None,
        country: str | None,
    ) -> bool:
        metadata_city = node.display_metadata.get("city")
        metadata_country = node.display_metadata.get("country")
        if city and normalize_text(str(metadata_city or "")) != city:
            return False
        if country and normalize_text(str(metadata_country or "")) != country:
            return False
        return True

    def stringify_time(self, value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str) and value.strip():
            return value
        return None
