from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from my_digital_brain.graph.models import GraphContextPackage, GraphViewNode, GraphViewResult

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


class GraphVectorizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    collection: str = MEMORY_DOCUMENTS_COLLECTION
    target_count: int = 0
    documents_built: int = 0
    embeddings_upserted: int = 0
    vector_records_upserted: int = 0
    unchanged_records: int = 0
    archived_records: int = 0
    skipped_targets: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class SemanticSearchTraceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    status: str = "ok"
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class SemanticMemoryHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    score: float
    source: Literal["semantic", "property"]
    vector_id: str | None = None
    distance: float | None = None
    collection: str = MEMORY_DOCUMENTS_COLLECTION
    embedding_scope: str | None = None
    primary_target_id: str
    primary_target_label: str
    canonical_target_id: str | None = None
    related_target_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    title: str | None = None
    description: str | None = None
    document_preview: str | None = None
    target: GraphViewNode | None = None
    canonical_target: GraphViewNode | None = None
    debug: dict[str, Any] = Field(default_factory=dict)


class SemanticMemorySearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    mode: Literal["semantic", "hybrid"] = "semantic"
    collection: str = MEMORY_DOCUMENTS_COLLECTION
    hits: list[SemanticMemoryHit] = Field(default_factory=list)
    graph_view: GraphViewResult
    context_packages: list[GraphContextPackage] = Field(default_factory=list)
    trace: list[SemanticSearchTraceEvent] = Field(default_factory=list)
