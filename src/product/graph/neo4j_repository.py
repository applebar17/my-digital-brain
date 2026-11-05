"""Neo4j adapter for the target typed semantic-node boundary."""

from datetime import UTC, datetime
from uuid import uuid4

from product.graph.models import (
    GRAPH_LABEL_BY_NODE_TYPE,
    NODE_CREATE_MODEL_BY_TYPE,
    GraphQueryExecutor,
    NodeCreate,
    NodeType,
    StoredNodeDTO,
)


class Neo4jNodeRepository:
    """Persist typed semantic nodes through a minimal Cypher executor."""

    def __init__(self, client: GraphQueryExecutor) -> None:
        self.client = client

    def search_nodes(
        self,
        owner_id: str,
        node_type: NodeType,
        terms: list[str],
        *,
        limit: int,
    ) -> list[StoredNodeDTO]:
        """Return bounded active same-type nodes matching readable identity terms."""
        self._required_text(owner_id, "owner_id")
        normalized_terms = self._unique_terms(terms)
        if not normalized_terms:
            return []
        label = GRAPH_LABEL_BY_NODE_TYPE[node_type]
        rows = self.client.execute_read(
            (
                f"MATCH (n:`{label}`) "
                "WHERE n.id <> $owner_id "
                "AND coalesce(n.lifecycle_state, 'active') = 'active' "
                "AND any(term IN $terms WHERE "
                "toLower(coalesce(n.display_name, n.name, n.title, '')) CONTAINS term "
                "OR any(alias IN coalesce(n.aliases, []) WHERE toLower(alias) CONTAINS term)) "
                "RETURN properties(n) AS properties LIMIT $limit"
            ),
            {"owner_id": owner_id, "terms": normalized_terms, "limit": limit},
        )
        return [self._stored_node(node_type, row) for row in rows]

    def get_node(
        self,
        owner_id: str,
        backend_id: str,
        node_type: NodeType,
    ) -> StoredNodeDTO:
        """Load one typed node or raise a readable boundary error."""
        self._required_text(owner_id, "owner_id")
        normalized_id = self._required_text(backend_id, "backend_id")
        label = GRAPH_LABEL_BY_NODE_TYPE[node_type]
        rows = self.client.execute_read(
            f"MATCH (n:`{label}` {{id: $id}}) RETURN properties(n) AS properties LIMIT 1",
            {"id": normalized_id},
        )
        if not rows:
            raise ValueError(
                f"No active {label} node exists for the supplied backend reference."
            )
        return self._stored_node(node_type, rows[0])

    def create_node(self, owner_id: str, node: NodeCreate) -> StoredNodeDTO:
        """Create one backend-owned node and return its typed representation."""
        self._required_text(owner_id, "owner_id")
        backend_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        properties = node.model_dump(mode="json", exclude={"node_type"})
        properties.update(
            {
                "id": backend_id,
                "created_at": now,
                "updated_at": now,
                "lifecycle_state": "active",
            }
        )
        label = GRAPH_LABEL_BY_NODE_TYPE[node.node_type]
        rows = self.client.execute_write(
            (
                f"CREATE (n:`{label}`) SET n = $properties "
                "RETURN properties(n) AS properties"
            ),
            {"properties": properties},
        )
        if len(rows) != 1:
            raise ValueError(f"Neo4j did not return the created {label} node.")
        return self._stored_node(node.node_type, rows[0])

    def update_node(
        self,
        owner_id: str,
        backend_id: str,
        node: NodeCreate,
    ) -> StoredNodeDTO:
        """Replace the explicit semantic fields of one existing typed node."""
        self._required_text(owner_id, "owner_id")
        normalized_id = self._required_text(backend_id, "backend_id")
        properties = node.model_dump(mode="json", exclude={"node_type"})
        properties["updated_at"] = datetime.now(UTC).isoformat()
        label = GRAPH_LABEL_BY_NODE_TYPE[node.node_type]
        rows = self.client.execute_write(
            (
                f"MATCH (n:`{label}` {{id: $id}}) SET n += $properties "
                "RETURN properties(n) AS properties"
            ),
            {"id": normalized_id, "properties": properties},
        )
        if len(rows) != 1:
            raise ValueError(f"No {label} node was updated for the supplied reference.")
        return self._stored_node(node.node_type, rows[0])

    @staticmethod
    def _stored_node(node_type: NodeType, row: dict[str, object]) -> StoredNodeDTO:
        properties = row.get("properties")
        if not isinstance(properties, dict):
            raise ValueError("Neo4j returned a node without a properties mapping.")
        backend_id = str(properties.get("id") or "").strip()
        if not backend_id:
            raise ValueError("Neo4j returned a node without its backend identifier.")
        model = NODE_CREATE_MODEL_BY_TYPE[node_type]
        values: dict[str, object] = {"node_type": node_type}
        for field_name in model.model_fields:
            if field_name == "node_type":
                continue
            if field_name == "aliases":
                aliases = properties.get(field_name)
                values[field_name] = list(aliases) if isinstance(aliases, list) else []
            else:
                values[field_name] = properties.get(field_name)
        return StoredNodeDTO(backend_id=backend_id, node=model.model_validate(values))

    @staticmethod
    def _unique_terms(terms: list[str]) -> list[str]:
        result: list[str] = []
        for term in terms:
            normalized = term.strip().casefold()
            if normalized and normalized not in result:
                result.append(normalized)
        return result

    @staticmethod
    def _required_text(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} must not be empty.")
        return normalized
