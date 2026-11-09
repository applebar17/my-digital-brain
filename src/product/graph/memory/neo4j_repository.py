"""Neo4j adapter for typed MemoryLog and Perception writes."""

from datetime import UTC, datetime
from uuid import uuid4

from product.graph.memory.models import (
    CreatePerceptionPersistenceDTO,
    MemoryLogWriteDTO,
    StoredMemoryLogDTO,
    StoredPerceptionDTO,
)
from product.graph.models import GraphQueryExecutor


class Neo4jMemoryRepository:
    """Persist memory objects and their required graph links atomically per object."""

    def __init__(self, client: GraphQueryExecutor) -> None:
        self.client = client

    def create_memory_log(
        self,
        owner_id: str,
        memory_log: MemoryLogWriteDTO,
    ) -> StoredMemoryLogDTO:
        """Create a MemoryLog linked to its primary host and involved targets."""
        backend_id = str(uuid4())
        properties = memory_log.model_dump(
            mode="json",
            exclude={"primary_host_backend_id", "involved_backend_ids"},
        )
        properties.update(self._backend_properties(owner_id, backend_id))
        rows = self.client.execute_write(
            (
                "MATCH (host {id: $primary_host_id}) "
                "OPTIONAL MATCH (involved) WHERE involved.id IN $involved_ids "
                "WITH host, collect(involved) AS involved_nodes "
                "WHERE size(involved_nodes) = size($involved_ids) "
                "CREATE (log:MemoryLog) SET log = $properties "
                "CREATE (host)-[:HAS_MEMORY_LOG {primary: true}]->(log) "
                "FOREACH (involved IN involved_nodes | "
                "  CREATE (log)-[:INVOLVES]->(involved)) "
                "RETURN log.id AS id"
            ),
            {
                "primary_host_id": memory_log.primary_host_backend_id,
                "involved_ids": memory_log.involved_backend_ids,
                "properties": properties,
            },
        )
        self._require_created(rows, "MemoryLog")
        return StoredMemoryLogDTO(backend_id=backend_id, memory_log=memory_log)

    def create_perception(
        self,
        owner_id: str,
        request: CreatePerceptionPersistenceDTO,
    ) -> StoredPerceptionDTO:
        """Create a Perception linked from its owner and to its target."""
        backend_id = str(uuid4())
        properties = request.perception.model_dump(mode="json")
        properties.update(self._backend_properties(owner_id, backend_id))
        rows = self.client.execute_write(
            (
                "MATCH (owner {id: $owner_id}), (target {id: $target_id}) "
                "CREATE (perception:Perception) SET perception = $properties "
                "CREATE (owner)-[:PERCEIVES]->(perception) "
                "CREATE (perception)-[:PERCEPTION_OF]->(target) "
                "CREATE (target)-[:HAS_AFFECTIVE_CONTEXT]->(perception) "
                "RETURN perception.id AS id"
            ),
            {
                "owner_id": owner_id,
                "target_id": request.target_backend_id,
                "properties": properties,
            },
        )
        self._require_created(rows, "Perception")
        return StoredPerceptionDTO(backend_id=backend_id, perception=request.perception)

    @staticmethod
    def _backend_properties(owner_id: str, backend_id: str) -> dict[str, object]:
        normalized_owner = owner_id.strip()
        if not normalized_owner:
            raise ValueError("owner_id must not be empty.")
        now = datetime.now(UTC).isoformat()
        return {
            "id": backend_id,
            "owner_id": normalized_owner,
            "created_at": now,
            "updated_at": now,
            "lifecycle_state": "active",
        }

    @staticmethod
    def _require_created(rows: list[dict[str, object]], label: str) -> None:
        if len(rows) != 1 or not str(rows[0].get("id") or "").strip():
            raise ValueError(
                f"Neo4j did not create {label}; verify that every referenced target exists."
            )
