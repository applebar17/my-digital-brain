from __future__ import annotations

from typing import TYPE_CHECKING, Any

from my_digital_brain.graph.registry import CORE_NODE_LABELS
from my_digital_brain.graph.repository_records import node_from_record, relationship_from_record

if TYPE_CHECKING:
    from my_digital_brain.storage.graph import GraphClient


class GraphMemoryRepository:
    def __init__(self, client: GraphClient) -> None:
        self.client = client

    def get_relationship_states(
        self,
        context_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        records = self.client.execute_read(
            """
            MATCH (:RelationshipContext {id: $context_id})-[:HAS_RELATIONSHIP_STATE]->
                  (state:RelationshipState)
            RETURN labels(state) AS labels, properties(state) AS properties
            ORDER BY coalesce(
                state.resolved_start,
                state.valid_from,
                state.observed_at,
                state.created_at,
                ""
            )
            LIMIT $limit
            """,
            {"context_id": context_id, "limit": limit},
        )
        return [node_from_record(record) for record in records]

    def clear_current_relationship_states(
        self,
        context_id: str,
        *,
        except_state_id: str,
        updated_at: str,
    ) -> list[dict[str, Any]]:
        records = self.client.execute_write(
            """
            MATCH (:RelationshipContext {id: $context_id})-[:HAS_RELATIONSHIP_STATE]->
                  (state:RelationshipState)
            WHERE state.id <> $except_state_id AND coalesce(state.is_current, false) = true
            SET state.is_current = false,
                state.updated_at = $updated_at
            RETURN labels(state) AS labels, properties(state) AS properties
            """,
            {
                "context_id": context_id,
                "except_state_id": except_state_id,
                "updated_at": updated_at,
            },
        )
        return [node_from_record(record) for record in records]

    def find_perceptions_for_target(
        self,
        node_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
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
        perceptions = [node_from_record(record) for record in records]

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
            node = node_from_record(record)
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
        contexts = [node_from_record(record) for record in records]

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
            node = node_from_record(record)
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
        return [relationship_from_record(record) for record in records]

    def find_change_records_for_target(
        self,
        target_id: str,
        *,
        target_kind: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        records = self.client.execute_read(
            """
            MATCH (c:ChangeRecord)
            WHERE c.target_id = $target_id
              AND ($target_kind IS NULL OR c.target_kind = $target_kind)
            RETURN labels(c) AS labels, properties(c) AS properties
            ORDER BY coalesce(c.changed_at, c.created_at, "") DESC
            LIMIT $limit
            """,
            {"target_id": target_id, "target_kind": target_kind, "limit": limit},
        )
        return [node_from_record(record) for record in records]

    def find_memory_logs_for_target(
        self,
        target_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        records = self.client.execute_read(
            """
            MATCH (target)-[:HAS_MEMORY_LOG]->(log:MemoryLog)
            WHERE target.id = $target_id
              AND any(label IN labels(target) WHERE label IN $core_labels)
            RETURN labels(log) AS labels, properties(log) AS properties
            ORDER BY coalesce(
                log.happened_at,
                log.resolved_start,
                log.source_time,
                log.observed_at,
                log.created_at,
                ""
            ) DESC
            LIMIT $limit
            """,
            {"target_id": target_id, "core_labels": list(CORE_NODE_LABELS), "limit": limit},
        )
        return [node_from_record(record) for record in records]

    def get_memory_log_detail(self, log_id: str, *, limit: int = 50) -> dict[str, Any] | None:
        log_records = self.client.execute_read(
            """
            MATCH (log:MemoryLog {id: $log_id})
            RETURN labels(log) AS labels, properties(log) AS properties
            LIMIT 1
            """,
            {"log_id": log_id},
        )
        if not log_records:
            return None

        relationship_records = self.client.execute_read(
            """
            MATCH (log:MemoryLog {id: $log_id})-[r]-(target)
            WHERE type(r) IN [
                "HAS_MEMORY_LOG",
                "INVOLVES",
                "UPDATES_RELATIONSHIP",
                "HAS_MEDIA"
            ]
            RETURN type(r) AS type,
                   startNode(r).id AS from_id,
                   endNode(r).id AS to_id,
                   properties(r) AS properties,
                   labels(target) AS target_labels,
                   properties(target) AS target_properties
            LIMIT $limit
            """,
            {"log_id": log_id, "limit": limit},
        )

        relationships = [relationship_from_record(record) for record in relationship_records]
        targets_by_id: dict[str, dict[str, Any]] = {}
        for record in relationship_records:
            target = node_from_record(
                {
                    "labels": record["target_labels"],
                    "properties": record["target_properties"],
                }
            )
            targets_by_id[target["properties"]["id"]] = target

        return {
            "memory_log": node_from_record(log_records[0]),
            "relationships": relationships,
            "targets": list(targets_by_id.values()),
        }

    def find_sources_for_target(
        self,
        target_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        records = self.client.execute_read(
            """
            MATCH (target)-[r]-(source:Source)
            WHERE target.id = $target_id
              AND any(label IN labels(target) WHERE label IN $core_labels)
              AND type(r) IN ["MENTIONED_IN", "SUPPORTED_BY", "DERIVED_FROM"]
            RETURN labels(source) AS labels, properties(source) AS properties
            LIMIT $limit
            """,
            {"target_id": target_id, "core_labels": list(CORE_NODE_LABELS), "limit": limit},
        )
        return [node_from_record(record) for record in records]

    def find_contradictions(
        self,
        *,
        target_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        contradiction_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        parameters = {
            "target_id": target_id,
            "status": status,
            "severity": severity,
            "contradiction_type": contradiction_type,
            "limit": limit,
        }
        if target_id:
            cypher = """
            MATCH (target)-[:HAS_CONTRADICTION_RECORD]->(c:ContradictionRecord)
            WHERE target.id = $target_id
              AND any(label IN labels(target) WHERE label IN $core_labels)
              AND ($status IS NULL OR c.status = $status)
              AND ($severity IS NULL OR c.severity = $severity)
              AND ($contradiction_type IS NULL OR c.contradiction_type = $contradiction_type)
            RETURN labels(c) AS labels, properties(c) AS properties
            ORDER BY coalesce(c.detected_at, c.created_at, "") DESC
            LIMIT $limit
            """
            parameters["core_labels"] = list(CORE_NODE_LABELS)
        else:
            cypher = """
            MATCH (c:ContradictionRecord)
            WHERE ($status IS NULL OR c.status = $status)
              AND ($severity IS NULL OR c.severity = $severity)
              AND ($contradiction_type IS NULL OR c.contradiction_type = $contradiction_type)
            RETURN labels(c) AS labels, properties(c) AS properties
            ORDER BY coalesce(c.detected_at, c.created_at, "") DESC
            LIMIT $limit
            """
        records = self.client.execute_read(cypher, parameters)
        return [node_from_record(record) for record in records]

    def find_merges(
        self,
        *,
        canonical_node_id: str | None = None,
        merged_node_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        records = self.client.execute_read(
            """
            MATCH (m:MergeRecord)
            WHERE ($canonical_node_id IS NULL OR m.canonical_node_id = $canonical_node_id)
              AND ($merged_node_id IS NULL OR $merged_node_id IN coalesce(m.merged_node_ids, []))
              AND ($status IS NULL OR m.status = $status)
            RETURN labels(m) AS labels, properties(m) AS properties
            ORDER BY coalesce(m.merged_at, m.created_at, "") DESC
            LIMIT $limit
            """,
            {
                "canonical_node_id": canonical_node_id,
                "merged_node_id": merged_node_id,
                "status": status,
                "limit": limit,
            },
        )
        return [node_from_record(record) for record in records]
