from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from my_digital_brain.graph.exceptions import GraphConflictError
from my_digital_brain.graph.models import NeighborhoodResult
from my_digital_brain.graph.registry import (
    CORE_NODE_LABELS,
    primary_core_label,
    validate_node_label,
    validate_relationship_direction,
    validate_relationship_type,
)
from my_digital_brain.graph.serialization import from_neo4j_properties, to_neo4j_properties

if TYPE_CHECKING:
    from my_digital_brain.storage.graph import GraphClient


class GraphRepository:
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
        return self._node_from_record(records[0])

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
        return self._node_from_record(records[0])

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
        return self._node_from_record(records[0])

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
            WHERE {label_filter}
              AND (
                $query IS NULL
                OR toLower(coalesce(
                    n.display_name,
                    n.name,
                    n.title,
                    n.text,
                    n.profile_key,
                    n.value,
                    n.description,
                    ""
                )) CONTAINS $query
                OR any(alias IN coalesce(n.aliases, []) WHERE toLower(alias) CONTAINS $query)
              )
              AND ($lifecycle_state IS NULL OR n.lifecycle_state = $lifecycle_state)
              AND ($privacy_level IS NULL OR n.privacy_level = $privacy_level)
              AND ($trust_level IS NULL OR n.trust_level = $trust_level)
            RETURN labels(n) AS labels, properties(n) AS properties
            LIMIT $limit
            """,
            parameters,
        )
        return [self._node_from_record(record) for record in records]

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
        return self._relationship_from_record(records[0])

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
        return [self._relationship_from_record(record) for record in records]

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
                node = self._node_from_record(node_record)
                nodes_by_id[node["properties"]["id"]] = node
            for relationship_record in record["relationships"]:
                relationship = self._relationship_from_record(relationship_record)
                relationships_by_id[relationship["properties"]["id"]] = relationship

        return NeighborhoodResult(
            nodes=list(nodes_by_id.values()),
            relationships=list(relationships_by_id.values()),
        )

    def find_perceptions_for_target(self, node_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        records = self.client.execute_read(
            """
            MATCH (target)
            WHERE target.id = $id AND any(label IN labels(target) WHERE label IN $core_labels)
            MATCH (p:Perception)-[:PERCEPTION_OF]->(target)
            RETURN labels(p) AS labels, properties(p) AS properties
            LIMIT $limit
            """,
            {"id": node_id, "core_labels": list(CORE_NODE_LABELS), "limit": limit},
        )
        perceptions = [self._node_from_record(record) for record in records]

        explicit_records = self.client.execute_read(
            """
            MATCH (target)-[:HAS_AFFECTIVE_CONTEXT]->(p:Perception)
            WHERE target.id = $id AND any(label IN labels(target) WHERE label IN $core_labels)
            RETURN labels(p) AS labels, properties(p) AS properties
            LIMIT $limit
            """,
            {"id": node_id, "core_labels": list(CORE_NODE_LABELS), "limit": limit},
        )
        by_id = {node["properties"]["id"]: node for node in perceptions}
        for record in explicit_records:
            node = self._node_from_record(record)
            by_id[node["properties"]["id"]] = node
        return list(by_id.values())

    def find_relationship_contexts_for_target(
        self,
        node_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        records = self.client.execute_read(
            """
            MATCH (rc:RelationshipContext)-[:RELATIONSHIP_WITH]->(target)
            WHERE target.id = $id AND any(label IN labels(target) WHERE label IN $core_labels)
            RETURN labels(rc) AS labels, properties(rc) AS properties
            LIMIT $limit
            """,
            {"id": node_id, "core_labels": list(CORE_NODE_LABELS), "limit": limit},
        )
        contexts = [self._node_from_record(record) for record in records]

        owned_records = self.client.execute_read(
            """
            MATCH (target)-[:HAS_RELATIONSHIP_CONTEXT]->(rc:RelationshipContext)
            WHERE target.id = $id AND any(label IN labels(target) WHERE label IN $core_labels)
            RETURN labels(rc) AS labels, properties(rc) AS properties
            LIMIT $limit
            """,
            {"id": node_id, "core_labels": list(CORE_NODE_LABELS), "limit": limit},
        )
        by_id = {node["properties"]["id"]: node for node in contexts}
        for record in owned_records:
            node = self._node_from_record(record)
            by_id[node["properties"]["id"]] = node
        return list(by_id.values())

    def find_affective_relationships(
        self,
        node_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        records = self.client.execute_read(
            """
            MATCH (n)-[r]-(m)
            WHERE n.id = $id
              AND any(label IN labels(n) WHERE label IN $core_labels)
              AND (
                r.emotional_summary IS NOT NULL
                OR r.emotional_valence IS NOT NULL
                OR r.original_user_words IS NOT NULL
                OR size(coalesce(r.emotion_tags, [])) > 0
              )
            RETURN type(r) AS type,
                   startNode(r).id AS from_id,
                   endNode(r).id AS to_id,
                   properties(r) AS properties
            LIMIT $limit
            """,
            {"id": node_id, "core_labels": list(CORE_NODE_LABELS), "limit": limit},
        )
        return [self._relationship_from_record(record) for record in records]

    def _node_from_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        labels = list(record["labels"])
        return {
            "label": primary_core_label(labels),
            "labels": labels,
            "properties": from_neo4j_properties(record["properties"]),
        }

    def _relationship_from_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "type": record["type"],
            "from_id": record["from_id"],
            "to_id": record["to_id"],
            "properties": from_neo4j_properties(record["properties"]),
        }


def raise_conflict_if_constraint_error(exc: Exception) -> None:
    class_name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    if "constraint" in class_name or "constraint" in message or "already exists" in message:
        raise GraphConflictError(str(exc)) from exc
