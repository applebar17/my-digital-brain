from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from my_digital_brain.graph.models import NeighborhoodResult
from my_digital_brain.graph.registry import (
    CORE_NODE_LABELS,
    CORE_RELATIONSHIP_TYPES,
    validate_node_label,
    validate_relationship_direction,
    validate_relationship_type,
)
from my_digital_brain.graph.repository_records import (
    node_from_record,
    raise_conflict_if_constraint_error,
    relationship_from_record,
)
from my_digital_brain.graph.serialization import to_neo4j_properties

if TYPE_CHECKING:
    from my_digital_brain.storage.graph import GraphClient


NODE_TEXT_SEARCH_FIELDS = [
    "display_name",
    "name",
    "normalized_name",
    "title",
    "text",
    "profile_key",
    "value",
    "description",
    "emotional_summary",
    "original_user_words",
    "relationship_type",
    "status",
    "closeness",
    "perception_type",
    "claim_type",
    "category",
    "source_type",
    "channel",
    "external_id",
    "city",
    "region",
    "country",
    "species",
    "breed",
    "circle_type",
    "source_kind",
    "owner_hint",
    "domain",
    "address",
    "label",
    "normalized_value",
    "kind",
]

NODE_LIST_SEARCH_FIELDS = [
    "aliases",
    "emotion_tags",
]


class GraphCoreRepository:
    def __init__(self, client: GraphClient) -> None:
        self.client = client

    def upsert_node(self, label: str, properties: Mapping[str, Any]) -> dict[str, Any]:
        label = validate_node_label(label)
        encoded = to_neo4j_properties(properties, exclude_none=True)
        node_id = encoded["id"]
        create_props = dict(encoded)
        update_props = {key: value for key, value in encoded.items() if key != "created_at"}

        try:
            records = self.client.execute_write(
                f"""
                MERGE (n:{label} {{id: $id}})
                ON CREATE SET n += $create_props
                SET n += $update_props
                RETURN labels(n) AS labels, properties(n) AS properties
                """,
                {"id": node_id, "create_props": create_props, "update_props": update_props},
            )
        except Exception as exc:
            raise_conflict_if_constraint_error(exc)
            raise
        return node_from_record(records[0])

    def patch_node(self, node_id: str, properties: Mapping[str, Any]) -> dict[str, Any] | None:
        encoded = to_neo4j_properties(properties, exclude_none=False)
        try:
            records = self.client.execute_write(
                """
                MATCH (n)
                WHERE n.id = $id AND any(label IN labels(n) WHERE label IN $core_labels)
                SET n += $properties
                RETURN labels(n) AS labels, properties(n) AS properties
                LIMIT 1
                """,
                {"id": node_id, "core_labels": list(CORE_NODE_LABELS), "properties": encoded},
            )
        except Exception as exc:
            raise_conflict_if_constraint_error(exc)
            raise
        if not records:
            return None
        return node_from_record(records[0])

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        records = self.client.execute_read(
            """
            MATCH (n)
            WHERE n.id = $id AND any(label IN labels(n) WHERE label IN $core_labels)
            RETURN labels(n) AS labels, properties(n) AS properties
            LIMIT 1
            """,
            {"id": node_id, "core_labels": list(CORE_NODE_LABELS)},
        )
        if not records:
            return None
        return node_from_record(records[0])

    def get_relationship(self, relationship_id: str) -> dict[str, Any] | None:
        records = self.client.execute_read(
            """
            MATCH ()-[r]->()
            WHERE r.id = $id AND type(r) IN $core_relationship_types
            RETURN type(r) AS type,
                   startNode(r).id AS from_id,
                   endNode(r).id AS to_id,
                   properties(r) AS properties
            LIMIT 1
            """,
            {
                "id": relationship_id,
                "core_relationship_types": list(CORE_RELATIONSHIP_TYPES),
            },
        )
        if not records:
            return None
        return relationship_from_record(records[0])

    def patch_relationship(
        self,
        relationship_id: str,
        properties: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        encoded = to_neo4j_properties(properties, exclude_none=False)
        records = self.client.execute_write(
            """
            MATCH ()-[r]->()
            WHERE r.id = $id AND type(r) IN $core_relationship_types
            SET r += $properties
            RETURN type(r) AS type,
                   startNode(r).id AS from_id,
                   endNode(r).id AS to_id,
                   properties(r) AS properties
            LIMIT 1
            """,
            {
                "id": relationship_id,
                "core_relationship_types": list(CORE_RELATIONSHIP_TYPES),
                "properties": encoded,
            },
        )
        if not records:
            return None
        return relationship_from_record(records[0])

    def search_nodes(
        self,
        *,
        label: str | None = None,
        query: str | None = None,
        lifecycle_state: str | None = None,
        privacy_level: str | None = None,
        trust_level: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        match_clause = "MATCH (n)"
        parameters: dict[str, Any] = {
            "core_labels": list(CORE_NODE_LABELS),
            "query": query.lower().strip() if query else None,
            "text_search_fields": NODE_TEXT_SEARCH_FIELDS,
            "list_search_fields": NODE_LIST_SEARCH_FIELDS,
            "lifecycle_state": lifecycle_state,
            "privacy_level": privacy_level,
            "trust_level": trust_level,
            "limit": limit,
        }
        label_filter = "any(label IN labels(n) WHERE label IN $core_labels)"
        if label:
            label = validate_node_label(label)
            match_clause = f"MATCH (n:{label})"
            label_filter = "true"

        records = self.client.execute_read(
            f"""
            {match_clause}
            WITH n, properties(n) AS props
            WHERE {label_filter}
              AND (
                $query IS NULL
                OR toLower(toString(props.id)) = $query
                OR any(
                    field IN $text_search_fields
                    WHERE props[field] IS NOT NULL
                      AND toLower(toString(props[field])) CONTAINS $query
                )
                OR any(
                    field IN $list_search_fields
                    WHERE props[field] IS NOT NULL
                      AND any(value IN props[field] WHERE toLower(toString(value)) CONTAINS $query)
                )
              )
              AND ($lifecycle_state IS NULL OR props.lifecycle_state = $lifecycle_state)
              AND ($privacy_level IS NULL OR props.privacy_level = $privacy_level)
              AND ($trust_level IS NULL OR props.trust_level = $trust_level)
            RETURN labels(n) AS labels, properties(n) AS properties
            LIMIT $limit
            """,
            parameters,
        )
        return [node_from_record(record) for record in records]

    def upsert_relationship(
        self,
        relationship_type: str,
        from_id: str,
        to_id: str,
        properties: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        relationship_type = validate_relationship_type(relationship_type)
        encoded = to_neo4j_properties(properties, exclude_none=True)
        relationship_id = encoded["id"]
        create_props = dict(encoded)
        update_props = {key: value for key, value in encoded.items() if key != "created_at"}

        records = self.client.execute_write(
            f"""
            MATCH (from_node)
            WHERE from_node.id = $from_id
              AND any(label IN labels(from_node) WHERE label IN $core_labels)
            MATCH (to_node)
            WHERE to_node.id = $to_id
              AND any(label IN labels(to_node) WHERE label IN $core_labels)
            MERGE (from_node)-[r:{relationship_type} {{id: $id}}]->(to_node)
            ON CREATE SET r += $create_props
            SET r += $update_props
            RETURN type(r) AS type,
                   startNode(r).id AS from_id,
                   endNode(r).id AS to_id,
                   properties(r) AS properties
            """,
            {
                "id": relationship_id,
                "from_id": from_id,
                "to_id": to_id,
                "core_labels": list(CORE_NODE_LABELS),
                "create_props": create_props,
                "update_props": update_props,
            },
        )
        if not records:
            return None
        return relationship_from_record(records[0])

    def get_node_relationships(
        self,
        node_id: str,
        *,
        relationship_type: str | None = None,
        direction: str = "both",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        validate_relationship_direction(direction)
        relationship_pattern = "[r]"
        if relationship_type:
            relationship_pattern = f"[r:{validate_relationship_type(relationship_type)}]"

        if direction == "out":
            path_pattern = f"(n)-{relationship_pattern}->(m)"
        elif direction == "in":
            path_pattern = f"(n)<-{relationship_pattern}-(m)"
        else:
            path_pattern = f"(n)-{relationship_pattern}-(m)"

        records = self.client.execute_read(
            f"""
            MATCH {path_pattern}
            WHERE n.id = $id AND any(label IN labels(n) WHERE label IN $core_labels)
            RETURN type(r) AS type,
                   startNode(r).id AS from_id,
                   endNode(r).id AS to_id,
                   properties(r) AS properties
            LIMIT $limit
            """,
            {"id": node_id, "core_labels": list(CORE_NODE_LABELS), "limit": limit},
        )
        return [relationship_from_record(record) for record in records]

    def get_related_records(
        self,
        node_id: str,
        *,
        depth: int = 1,
        limit: int = 50,
    ) -> NeighborhoodResult:
        return self.get_neighborhood(node_id, depth=depth, limit=limit)

    def get_neighborhood(
        self,
        node_id: str,
        *,
        depth: int = 1,
        limit: int = 50,
    ) -> NeighborhoodResult:
        records = self.client.execute_read(
            f"""
            MATCH path = (n)-[*1..{depth}]-(m)
            WHERE n.id = $id AND any(label IN labels(n) WHERE label IN $core_labels)
            RETURN [node IN nodes(path) | {{
                       labels: labels(node),
                       properties: properties(node)
                   }}] AS nodes,
                   [rel IN relationships(path) | {{
                       type: type(rel),
                       from_id: startNode(rel).id,
                       to_id: endNode(rel).id,
                       properties: properties(rel)
                   }}] AS relationships
            LIMIT $limit
            """,
            {"id": node_id, "core_labels": list(CORE_NODE_LABELS), "limit": limit},
        )

        nodes_by_id: dict[str, dict[str, Any]] = {}
        relationships_by_id: dict[str, dict[str, Any]] = {}
        for record in records:
            for node_record in record["nodes"]:
                node = node_from_record(node_record)
                nodes_by_id[node["properties"]["id"]] = node
            for relationship_record in record["relationships"]:
                relationship = relationship_from_record(relationship_record)
                relationships_by_id[relationship["properties"]["id"]] = relationship

        return NeighborhoodResult(
            nodes=list(nodes_by_id.values()),
            relationships=list(relationships_by_id.values()),
        )
