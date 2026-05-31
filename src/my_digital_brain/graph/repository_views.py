from __future__ import annotations

from typing import TYPE_CHECKING, Any

from my_digital_brain.graph.models import NeighborhoodResult
from my_digital_brain.graph.registry import CORE_NODE_LABELS, CORE_RELATIONSHIP_TYPES
from my_digital_brain.graph.repository_records import node_from_record, relationship_from_record

if TYPE_CHECKING:
    from my_digital_brain.storage.graph import GraphClient


class GraphViewRepository:
    def __init__(self, client: GraphClient) -> None:
        self.client = client

    def find_map_records(
        self,
        *,
        city: str | None = None,
        country: str | None = None,
        limit: int = 100,
    ) -> NeighborhoodResult:
        records = self.client.execute_read(
            """
            MATCH (place:Place)
            WHERE ($city IS NULL OR toLower(coalesce(place.city, "")) = $city)
              AND ($country IS NULL OR toLower(coalesce(place.country, "")) = $country)
              AND (
                place.latitude IS NOT NULL
                OR place.longitude IS NOT NULL
                OR $city IS NOT NULL
                OR $country IS NOT NULL
              )
            OPTIONAL MATCH (event:Event)-[r:HAPPENED_AT]->(place)
            RETURN labels(place) AS place_labels,
                   properties(place) AS place_properties,
                   labels(event) AS event_labels,
                   properties(event) AS event_properties,
                   type(r) AS relationship_type,
                   CASE WHEN r IS NULL THEN NULL ELSE startNode(r).id END AS from_id,
                   CASE WHEN r IS NULL THEN NULL ELSE endNode(r).id END AS to_id,
                   properties(r) AS relationship_properties
            LIMIT $limit
            """,
            {
                "city": city.lower().strip() if city else None,
                "country": country.lower().strip() if country else None,
                "limit": limit,
            },
        )
        nodes_by_id: dict[str, dict[str, Any]] = {}
        relationships_by_id: dict[str, dict[str, Any]] = {}
        for record in records:
            place = node_from_record(
                {"labels": record["place_labels"], "properties": record["place_properties"]}
            )
            nodes_by_id[place["properties"]["id"]] = place
            if record["event_properties"]:
                event = node_from_record(
                    {"labels": record["event_labels"], "properties": record["event_properties"]}
                )
                nodes_by_id[event["properties"]["id"]] = event
            if record["relationship_properties"]:
                relationship = relationship_from_record(
                    {
                        "type": record["relationship_type"],
                        "from_id": record["from_id"],
                        "to_id": record["to_id"],
                        "properties": record["relationship_properties"],
                    }
                )
                relationships_by_id[relationship["properties"]["id"]] = relationship
        return NeighborhoodResult(
            nodes=list(nodes_by_id.values()),
            relationships=list(relationships_by_id.values()),
        )

    def count_nodes_by_label(self, *, include_archived: bool = False) -> dict[str, int]:
        records = self.client.execute_read(
            """
            MATCH (n)
            WHERE any(label IN labels(n) WHERE label IN $core_labels)
              AND (
                $include_archived = true
                OR coalesce(n.lifecycle_state, "active") <> "archived"
              )
              AND ($include_archived = true OR n.merged_into_id IS NULL)
            UNWIND labels(n) AS label
            WITH label, n
            WHERE label IN $core_labels
            RETURN label, count(n) AS count
            """,
            {"core_labels": list(CORE_NODE_LABELS), "include_archived": include_archived},
        )
        return {record["label"]: record["count"] for record in records}

    def count_relationships_by_type(self) -> dict[str, int]:
        records = self.client.execute_read(
            """
            MATCH ()-[r]->()
            WHERE type(r) IN $core_relationship_types
            RETURN type(r) AS type, count(r) AS count
            """,
            {"core_relationship_types": list(CORE_RELATIONSHIP_TYPES)},
        )
        return {record["type"]: record["count"] for record in records}

    def top_connected_nodes(
        self,
        *,
        include_archived: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        records = self.client.execute_read(
            """
            MATCH (n)-[r]-()
            WHERE any(label IN labels(n) WHERE label IN $core_labels)
              AND (
                $include_archived = true
                OR coalesce(n.lifecycle_state, "active") <> "archived"
              )
              AND ($include_archived = true OR n.merged_into_id IS NULL)
            RETURN labels(n) AS labels, properties(n) AS properties, count(r) AS count
            ORDER BY count DESC
            LIMIT $limit
            """,
            {
                "core_labels": list(CORE_NODE_LABELS),
                "include_archived": include_archived,
                "limit": limit,
            },
        )
        return [{"node": node_from_record(record), "count": record["count"]} for record in records]

    def top_emotion_tags(
        self,
        *,
        include_archived: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        records = self.client.execute_read(
            """
            MATCH (n)
            WHERE any(label IN labels(n) WHERE label IN $core_labels)
              AND size(coalesce(n.emotion_tags, [])) > 0
              AND (
                $include_archived = true
                OR coalesce(n.lifecycle_state, "active") <> "archived"
              )
              AND ($include_archived = true OR n.merged_into_id IS NULL)
            UNWIND n.emotion_tags AS tag
            RETURN tag, count(*) AS count
            ORDER BY count DESC
            LIMIT $limit
            """,
            {
                "core_labels": list(CORE_NODE_LABELS),
                "include_archived": include_archived,
                "limit": limit,
            },
        )
        return records

    def count_unresolved_contradictions(self) -> int:
        records = self.client.execute_read(
            """
            MATCH (c:ContradictionRecord)
            WHERE coalesce(c.status, "detected") IN ["detected", "needs_clarification"]
            RETURN count(c) AS count
            """
        )
        return records[0]["count"] if records else 0
