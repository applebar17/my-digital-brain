"""Neo4j adapter for direct relationships and relationship history."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from product.graph.models import GraphQueryExecutor
from product.graph.relationships.models import (
    AppendRelationshipStatePersistenceDTO,
    CreateRelationshipContextPersistenceDTO,
    CreateRelationshipPersistenceDTO,
    DirectRelationshipDTO,
    GraphRelationshipRepository,
    RelationshipContextDetailDTO,
    RelationshipContextDTO,
    RelationshipStateDTO,
    RelationshipType,
    StoredDirectRelationshipDTO,
    StoredRelationshipContextDTO,
    StoredRelationshipStateDTO,
    UpdateRelationshipPersistenceDTO,
)


class Neo4jRelationshipRepository(GraphRelationshipRepository):
    """Persist semantic edges and append-only relationship history in Neo4j."""

    def __init__(self, client: GraphQueryExecutor) -> None:
        self.client = client

    def create_or_get_relationship(
        self,
        owner_id: str,
        request: CreateRelationshipPersistenceDTO,
    ) -> StoredDirectRelationshipDTO:
        """Create an exact type/endpoints edge without changing an existing edge."""
        new_id = str(uuid4())
        relationship_type = request.relationship.relationship_type.value
        properties = request.relationship.model_dump(
            mode="json",
            exclude={"relationship_type"},
        )
        properties.update(self._creation_properties(owner_id, new_id))
        rows = self.client.execute_write(
            (
                "MATCH (source {id: $from_id}), (target {id: $to_id}) "
                f"MERGE (source)-[relationship:`{relationship_type}` "
                "{owner_id: $owner_id}]->(target) "
                "ON CREATE SET relationship = $properties "
                "RETURN relationship.id AS id, relationship.id = $new_id AS created, "
                "properties(relationship) AS properties"
            ),
            {
                "owner_id": owner_id,
                "from_id": request.from_backend_id,
                "to_id": request.to_backend_id,
                "new_id": new_id,
                "properties": properties,
            },
        )
        row = self._one(rows, "direct relationship")
        return self._stored_relationship(
            row,
            relationship_type=request.relationship.relationship_type,
            from_backend_id=request.from_backend_id,
            to_backend_id=request.to_backend_id,
        )

    def update_relationship(
        self,
        owner_id: str,
        request: UpdateRelationshipPersistenceDTO,
    ) -> StoredDirectRelationshipDTO:
        """Update only explicitly supplied semantic fields on one owner edge."""
        properties = request.patch.model_dump(exclude_none=True)
        properties["updated_at"] = self._now()
        rows = self.client.execute_write(
            (
                "MATCH (source)-[relationship]->(target) "
                "WHERE relationship.id = $id AND relationship.owner_id = $owner_id "
                "SET relationship += $properties "
                "RETURN relationship.id AS id, false AS created, type(relationship) AS type, "
                "source.id AS from_id, target.id AS to_id, "
                "properties(relationship) AS properties"
            ),
            {
                "id": request.relationship_backend_id,
                "owner_id": owner_id,
                "properties": properties,
            },
        )
        row = self._one(rows, "relationship update")
        return self._stored_relationship(
            row,
            relationship_type=RelationshipType(str(row.get("type") or "")),
            from_backend_id=str(row.get("from_id") or ""),
            to_backend_id=str(row.get("to_id") or ""),
        )

    def create_or_get_context(
        self,
        owner_id: str,
        request: CreateRelationshipContextPersistenceDTO,
    ) -> StoredRelationshipContextDTO:
        """Create or reuse the exact owner/participant-set/category context."""
        participant_ids = sorted(set(request.participant_backend_ids))
        memory_ids = sorted(set(request.memory_log_backend_ids))
        context_key = self._context_key(owner_id, participant_ids, request.context.category.value)
        new_id = str(uuid4())
        properties = request.context.model_dump(mode="json")
        properties.update(self._creation_properties(owner_id, new_id))
        properties["context_key"] = context_key
        rows = self.client.execute_write(
            (
                "MATCH (participant) WHERE participant.id IN $participant_ids "
                "WITH collect(DISTINCT participant) AS participants "
                "WHERE size(participants) = size($participant_ids) "
                "OPTIONAL MATCH (memory:MemoryLog) WHERE memory.id IN $memory_ids "
                "WITH participants, collect(DISTINCT memory) AS memories "
                "WHERE size(memories) = size($memory_ids) "
                "MERGE (context:RelationshipContext "
                "{owner_id: $owner_id, context_key: $context_key}) "
                "ON CREATE SET context = $properties "
                "FOREACH (participant IN participants | "
                "  MERGE (context)-[:RELATIONSHIP_WITH]->(participant) "
                "  MERGE (participant)-[:HAS_RELATIONSHIP_CONTEXT]->(context)) "
                "FOREACH (memory IN memories | "
                "  MERGE (memory)-[:UPDATES_RELATIONSHIP]->(context)) "
                "RETURN context.id AS id, context.id = $new_id AS created, "
                "properties(context) AS properties"
            ),
            {
                "owner_id": owner_id,
                "participant_ids": participant_ids,
                "memory_ids": memory_ids,
                "context_key": context_key,
                "new_id": new_id,
                "properties": properties,
            },
        )
        row = self._one(rows, "relationship context")
        return StoredRelationshipContextDTO(
            backend_id=str(row["id"]),
            participant_backend_ids=participant_ids,
            memory_log_backend_ids=memory_ids,
            context=self._context_from_properties(row),
            created=bool(row.get("created")),
        )

    def append_state(
        self,
        owner_id: str,
        request: AppendRelationshipStatePersistenceDTO,
    ) -> StoredRelationshipStateDTO:
        """Append or exact-reuse one state and link its supporting memories."""
        memory_ids = sorted(set(request.memory_log_backend_ids))
        fingerprint = self._state_fingerprint(request.context_backend_id, request.state)
        new_id = str(uuid4())
        properties = request.state.model_dump(mode="json")
        properties.update(self._creation_properties(owner_id, new_id))
        properties.update(
            {"context_id": request.context_backend_id, "fingerprint": fingerprint}
        )
        rows = self.client.execute_write(
            (
                "MATCH (context:RelationshipContext "
                "{id: $context_id, owner_id: $owner_id}) "
                "OPTIONAL MATCH (memory:MemoryLog) WHERE memory.id IN $memory_ids "
                "WITH context, collect(DISTINCT memory) AS memories "
                "WHERE size(memories) = size($memory_ids) "
                "MERGE (state:RelationshipState "
                "{owner_id: $owner_id, context_id: $context_id, fingerprint: $fingerprint}) "
                "ON CREATE SET state = $properties "
                "MERGE (context)-[:HAS_RELATIONSHIP_STATE]->(state) "
                "FOREACH (memory IN memories | "
                "  MERGE (memory)-[:UPDATES_RELATIONSHIP]->(context)) "
                "RETURN state.id AS id, state.id = $new_id AS created, "
                "properties(state) AS properties"
            ),
            {
                "owner_id": owner_id,
                "context_id": request.context_backend_id,
                "memory_ids": memory_ids,
                "fingerprint": fingerprint,
                "new_id": new_id,
                "properties": properties,
            },
        )
        row = self._one(rows, "relationship state")
        return StoredRelationshipStateDTO(
            backend_id=str(row["id"]),
            context_backend_id=request.context_backend_id,
            memory_log_backend_ids=memory_ids,
            state=self._state_from_properties(row),
            created=bool(row.get("created")),
        )

    def get_context_detail(
        self,
        owner_id: str,
        context_backend_id: str,
        *,
        state_limit: int,
    ) -> RelationshipContextDetailDTO:
        """Return context participants, linked memories, and bounded recent states."""
        context_rows = self.client.execute_read(
            (
                "MATCH (context:RelationshipContext {id: $id, owner_id: $owner_id}) "
                "OPTIONAL MATCH (context)-[:RELATIONSHIP_WITH]->(participant) "
                "WITH context, collect(DISTINCT participant.id) AS participant_ids "
                "OPTIONAL MATCH (memory:MemoryLog)-[:UPDATES_RELATIONSHIP]->(context) "
                "RETURN context.id AS id, properties(context) AS properties, "
                "participant_ids, collect(DISTINCT memory.id) AS memory_ids"
            ),
            {"id": context_backend_id, "owner_id": owner_id},
        )
        context_row = self._one(context_rows, "relationship context detail")
        state_rows = self.client.execute_read(
            (
                "MATCH (:RelationshipContext {id: $id, owner_id: $owner_id})"
                "-[:HAS_RELATIONSHIP_STATE]->(state:RelationshipState) "
                "RETURN state.id AS id, properties(state) AS properties "
                "ORDER BY coalesce(state.valid_from, state.created_at) DESC "
                "LIMIT $limit"
            ),
            {"id": context_backend_id, "owner_id": owner_id, "limit": state_limit},
        )
        context = StoredRelationshipContextDTO(
            backend_id=str(context_row["id"]),
            participant_backend_ids=self._strings(context_row.get("participant_ids")),
            memory_log_backend_ids=self._strings(context_row.get("memory_ids")),
            context=self._context_from_properties(context_row),
            created=False,
        )
        states = [
            StoredRelationshipStateDTO(
                backend_id=str(row["id"]),
                context_backend_id=context_backend_id,
                memory_log_backend_ids=[],
                state=self._state_from_properties(row),
                created=False,
            )
            for row in state_rows
        ]
        return RelationshipContextDetailDTO(relationship_context=context, states=states)

    def _stored_relationship(
        self,
        row: dict[str, object],
        *,
        relationship_type: RelationshipType,
        from_backend_id: str,
        to_backend_id: str,
    ) -> StoredDirectRelationshipDTO:
        properties = self._properties(row)
        return StoredDirectRelationshipDTO(
            backend_id=str(row["id"]),
            from_backend_id=from_backend_id,
            to_backend_id=to_backend_id,
            relationship=DirectRelationshipDTO(
                relationship_type=relationship_type,
                description=self._optional(properties.get("description")),
                relationship_detail=self._optional(properties.get("relationship_detail")),
                valid_from=self._optional(properties.get("valid_from")),
                valid_to=self._optional(properties.get("valid_to")),
                original_user_words=self._optional(properties.get("original_user_words")),
            ),
            created=bool(row.get("created")),
        )

    def _context_from_properties(self, row: dict[str, object]) -> RelationshipContextDTO:
        properties = self._properties(row)
        return RelationshipContextDTO(
            category=str(properties.get("category") or ""),
            description=str(properties.get("description") or ""),
            relationship_kind=self._optional(properties.get("relationship_kind")),
            original_user_words=self._optional(properties.get("original_user_words")),
        )

    def _state_from_properties(self, row: dict[str, object]) -> RelationshipStateDTO:
        properties = self._properties(row)
        tags = properties.get("emotion_tags")
        return RelationshipStateDTO(
            status=self._optional(properties.get("status")),
            closeness=self._optional(properties.get("closeness")),
            description=self._optional(properties.get("description")),
            emotional_summary=self._optional(properties.get("emotional_summary")),
            emotional_valence=self._optional(properties.get("emotional_valence")),
            emotion_tags=list(tags) if isinstance(tags, list) else [],
            original_user_words=self._optional(properties.get("original_user_words")),
            valid_from=self._optional(properties.get("valid_from")),
            valid_to=self._optional(properties.get("valid_to")),
            time_precision=self._optional(properties.get("time_precision")),
        )

    @staticmethod
    def _context_key(owner_id: str, participant_ids: list[str], category: str) -> str:
        raw = json.dumps([owner_id, participant_ids, category], separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _state_fingerprint(context_id: str, state: RelationshipStateDTO) -> str:
        raw = json.dumps(
            [context_id, state.model_dump(mode="json")],
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def _creation_properties(cls, owner_id: str, backend_id: str) -> dict[str, object]:
        if not owner_id.strip():
            raise ValueError("owner_id must not be empty.")
        now = cls._now()
        return {
            "id": backend_id,
            "owner_id": owner_id,
            "created_at": now,
            "updated_at": now,
            "lifecycle_state": "active",
        }

    @staticmethod
    def _properties(row: dict[str, object]) -> dict[str, object]:
        properties = row.get("properties")
        if not isinstance(properties, dict):
            raise ValueError("Neo4j returned a record without typed properties.")
        return properties

    @staticmethod
    def _one(rows: list[dict[str, object]], operation: str) -> dict[str, object]:
        if len(rows) != 1 or not str(rows[0].get("id") or "").strip():
            raise ValueError(
                f"Neo4j could not complete {operation}; verify every supplied reference."
            )
        return rows[0]

    @staticmethod
    def _strings(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item is not None]

    @staticmethod
    def _optional(value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()
