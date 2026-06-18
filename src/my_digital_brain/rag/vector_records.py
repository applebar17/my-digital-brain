from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.rag.models import StoredVectorRecord, VectorRecordData
from my_digital_brain.storage.relational import RelationalSessionProvider
from my_digital_brain.storage.relational_models import VectorRecord


class VectorRecordStore:
    """Relational operational store for Chroma-to-Neo4j vector references."""

    def __init__(self, sessions: RelationalSessionProvider) -> None:
        self.sessions = sessions

    def upsert(self, data: VectorRecordData) -> StoredVectorRecord:
        now = _utc_now()
        with self.sessions.session() as db:
            record = db.scalar(
                select(VectorRecord).where(
                    VectorRecord.vector_store == data.vector_store,
                    VectorRecord.collection == data.collection,
                    VectorRecord.vector_id == data.vector_id,
                ),
            )
            if record is None:
                record = VectorRecord(
                    id=new_uuid(),
                    created_at=now,
                    updated_at=now,
                    vector_store=data.vector_store,
                    collection=data.collection,
                    vector_id=data.vector_id,
                    graph_id=data.primary_target_id,
                    source_id=data.source_ids[0] if data.source_ids else None,
                    metadata_json=_metadata_json(data),
                    embedding_scope=data.embedding_scope,
                    primary_target_id=data.primary_target_id,
                    primary_target_label=data.primary_target_label,
                    related_target_ids_json=list(data.related_target_ids),
                    source_ids_json=list(data.source_ids),
                    relationship_ids_json=list(data.relationship_ids),
                    embedding_model=data.embedding_model,
                    builder_version=data.builder_version,
                    document_checksum=data.document_checksum,
                    lifecycle_state=data.lifecycle_state,
                )
                db.add(record)
            else:
                _apply_data(record, data, updated_at=now)
            db.flush()
            return _from_record(record)

    def get_by_vector_id(
        self,
        vector_id: str,
        *,
        vector_store: str,
        collection: str,
    ) -> StoredVectorRecord | None:
        with self.sessions.session() as db:
            record = db.scalar(
                select(VectorRecord).where(
                    VectorRecord.vector_store == vector_store,
                    VectorRecord.collection == collection,
                    VectorRecord.vector_id == vector_id,
                ),
            )
            return _from_record(record) if record is not None else None

    def list_by_primary_target(
        self,
        primary_target_id: str,
        *,
        collection: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[StoredVectorRecord]:
        with self.sessions.session() as db:
            statement = select(VectorRecord).where(
                VectorRecord.primary_target_id == primary_target_id,
            )
            if collection is not None:
                statement = statement.where(VectorRecord.collection == collection)
            if not include_archived:
                statement = statement.where(VectorRecord.lifecycle_state != "archived")
            statement = statement.order_by(VectorRecord.updated_at.desc()).limit(max(0, limit))
            return [_from_record(record) for record in db.scalars(statement)]

    def mark_lifecycle_state(
        self,
        vector_id: str,
        lifecycle_state: str,
        *,
        vector_store: str,
        collection: str,
    ) -> StoredVectorRecord | None:
        now = _utc_now()
        with self.sessions.session() as db:
            record = db.scalar(
                select(VectorRecord).where(
                    VectorRecord.vector_store == vector_store,
                    VectorRecord.collection == collection,
                    VectorRecord.vector_id == vector_id,
                ),
            )
            if record is None:
                return None
            record.lifecycle_state = lifecycle_state
            record.updated_at = now
            db.flush()
            return _from_record(record)


def _apply_data(record: VectorRecord, data: VectorRecordData, *, updated_at: datetime) -> None:
    record.updated_at = updated_at
    record.graph_id = data.primary_target_id
    record.source_id = data.source_ids[0] if data.source_ids else None
    record.embedding_scope = data.embedding_scope
    record.primary_target_id = data.primary_target_id
    record.primary_target_label = data.primary_target_label
    record.metadata_json = _metadata_json(data)
    record.related_target_ids_json = list(data.related_target_ids)
    record.source_ids_json = list(data.source_ids)
    record.relationship_ids_json = list(data.relationship_ids)
    record.embedding_model = data.embedding_model
    record.builder_version = data.builder_version
    record.document_checksum = data.document_checksum
    record.lifecycle_state = data.lifecycle_state


def _from_record(record: VectorRecord) -> StoredVectorRecord:
    metadata = dict(record.metadata_json or {})
    return StoredVectorRecord(
        id=record.id,
        created_at=record.created_at,
        updated_at=record.updated_at,
        vector_store=record.vector_store,
        collection=record.collection,
        vector_id=record.vector_id,
        embedding_scope=record.embedding_scope or "",
        primary_target_id=record.primary_target_id or record.graph_id or "",
        primary_target_label=record.primary_target_label or "",
        canonical_target_id=_optional_str(metadata.get("canonical_target_id")),
        related_target_ids=list(record.related_target_ids_json or []),
        source_ids=list(record.source_ids_json or ([record.source_id] if record.source_id else [])),
        relationship_ids=list(record.relationship_ids_json or []),
        hit_role=_hit_role(metadata.get("hit_role"), record.primary_target_label),
        embedding_model=record.embedding_model,
        builder_version=record.builder_version or "",
        document_checksum=record.document_checksum or "",
        lifecycle_state=record.lifecycle_state,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _metadata_json(data: VectorRecordData) -> dict[str, str]:
    metadata: dict[str, str] = {"hit_role": data.hit_role}
    if data.canonical_target_id:
        metadata["canonical_target_id"] = data.canonical_target_id
    return metadata


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _hit_role(value: object, primary_target_label: str | None) -> str:
    if value in {"domain_node", "context", "memory_log"}:
        return str(value)
    if primary_target_label == "MemoryLog":
        return "memory_log"
    if primary_target_label in {
        "Claim",
        "Perception",
        "RelationshipContext",
        "RelationshipState",
        "ProfileMemory",
    }:
        return "context"
    return "domain_node"
