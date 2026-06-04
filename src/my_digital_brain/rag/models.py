from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

MEMORY_DOCUMENTS_COLLECTION = "memory_documents"
VECTOR_STORE_CHROMA = "chroma"


class EmbeddingDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vector_id: str
    collection: str = MEMORY_DOCUMENTS_COLLECTION
    embedding_scope: str
    primary_target_id: str
    primary_target_label: str
    related_target_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    embedding_model: str | None = None
    builder_version: str
    document_checksum: str
    lifecycle_state: str = "active"
    document: str

    @field_validator("primary_target_id", "primary_target_label", "embedding_scope", "builder_version")
    @classmethod
    def _require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Field must not be empty.")
        return value

    @field_validator("related_target_ids", "source_ids", "relationship_ids")
    @classmethod
    def _dedupe_ids(cls, values: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                deduped.append(value)
        return deduped


class VectorRecordData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vector_store: str = VECTOR_STORE_CHROMA
    collection: str = MEMORY_DOCUMENTS_COLLECTION
    vector_id: str
    embedding_scope: str
    primary_target_id: str
    primary_target_label: str
    related_target_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    embedding_model: str | None = None
    builder_version: str
    document_checksum: str
    lifecycle_state: str = "active"

    @classmethod
    def from_embedding_document(
        cls,
        document: EmbeddingDocument,
        *,
        vector_store: str = VECTOR_STORE_CHROMA,
    ) -> "VectorRecordData":
        return cls(
            vector_store=vector_store,
            collection=document.collection,
            vector_id=document.vector_id,
            embedding_scope=document.embedding_scope,
            primary_target_id=document.primary_target_id,
            primary_target_label=document.primary_target_label,
            related_target_ids=document.related_target_ids,
            source_ids=document.source_ids,
            relationship_ids=document.relationship_ids,
            embedding_model=document.embedding_model,
            builder_version=document.builder_version,
            document_checksum=document.document_checksum,
            lifecycle_state=document.lifecycle_state,
        )


class StoredVectorRecord(VectorRecordData):
    id: str
    created_at: datetime
    updated_at: datetime
