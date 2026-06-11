from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from my_digital_brain.ingestion.contracts.base import IngestionModel

V1_VECTOR_DIMENSIONS = 512


class VectorScopeName(StrEnum):
    MEMORY_NODE_SUMMARIES = "memory_node_summaries"
    MEMORY_CONTEXTS = "memory_contexts"
    MEMORY_MICRO_LOGS = "memory_micro_logs"


class VectorQueryStrategy(StrEnum):
    SINGLE_SHARED_DIMENSION = "single_shared_dimension"
    PER_SCOPE_EMBEDDING = "per_scope_embedding"
    MAX_DIMENSION_PREFIX_TRUNCATION = "max_dimension_prefix_truncation"


class VectorScopeConfig(IngestionModel):
    scope: VectorScopeName = Field(description="Logical retrieval scope.")
    collection: str = Field(description="Vector collection name for this scope.")
    dimensions: int = Field(
        default=V1_VECTOR_DIMENSIONS,
        description="Embedding dimensions. V1 locks every scope to 512.",
    )
    embedding_model: str | None = Field(
        default=None,
        description="Embedding model override. None means use configured default.",
    )
    enabled: bool = True
    ranking_weight: float = Field(
        default=1.0,
        gt=0.0,
        description="Scope-level ranking multiplier used after retrieval.",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable scope purpose.",
    )

    @model_validator(mode="after")
    def _validate_v1_dimensions(self) -> "VectorScopeConfig":
        if self.dimensions != V1_VECTOR_DIMENSIONS:
            raise ValueError("V1 vector scope dimensions must be 512.")
        return self


class MultiScopeVectorConfig(IngestionModel):
    query_strategy: VectorQueryStrategy = Field(
        default=VectorQueryStrategy.SINGLE_SHARED_DIMENSION,
        description="V1 uses one shared query embedding for all enabled scopes.",
    )
    dimensions: int = Field(
        default=V1_VECTOR_DIMENSIONS,
        description="Shared v1 query/document embedding dimensions.",
    )
    scopes: list[VectorScopeConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_shared_v1_scope_config(self) -> "MultiScopeVectorConfig":
        if self.query_strategy != VectorQueryStrategy.SINGLE_SHARED_DIMENSION:
            raise ValueError(
                "Wave 0 only locks the single_shared_dimension v1 query strategy."
            )
        if self.dimensions != V1_VECTOR_DIMENSIONS:
            raise ValueError("V1 multi-scope vector config dimensions must be 512.")
        seen: set[VectorScopeName] = set()
        for scope in self.scopes:
            if scope.scope in seen:
                raise ValueError(f"Duplicate vector scope: {scope.scope}")
            seen.add(scope.scope)
            if scope.dimensions != self.dimensions:
                raise ValueError("All v1 vector scopes must share 512 dimensions.")
        return self


class VectorScopeSearchRequest(IngestionModel):
    query_text: str = Field(description="Natural language query to embed once for v1 search.")
    enabled_scopes: list[VectorScopeName] = Field(
        default_factory=list,
        description="Scopes to search with the shared 512-dimensional query embedding.",
    )
    dimensions: int = Field(default=V1_VECTOR_DIMENSIONS)
    limit_per_scope: int = Field(default=10, ge=1)

    @model_validator(mode="after")
    def _validate_search_dimensions(self) -> "VectorScopeSearchRequest":
        if self.dimensions != V1_VECTOR_DIMENSIONS:
            raise ValueError("V1 vector search request dimensions must be 512.")
        if not self.query_text.strip():
            raise ValueError("VectorScopeSearchRequest requires non-empty query_text.")
        return self


class VectorScopeHitRef(IngestionModel):
    scope: VectorScopeName
    collection: str
    vector_id: str
    score: float = Field(ge=0.0)
    primary_target_id: str
    primary_target_label: str
    canonical_target_id: str | None = None
    related_target_ids: list[str] = Field(default_factory=list)
    hit_role: Literal["domain_node", "context", "memory_log"] = Field(
        description="How retrieval should hydrate/render this hit.",
    )


class MultiScopeRetrievalResult(IngestionModel):
    query_text: str
    dimensions: int = Field(default=V1_VECTOR_DIMENSIONS)
    hits: list[VectorScopeHitRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_result_dimensions(self) -> "MultiScopeRetrievalResult":
        if self.dimensions != V1_VECTOR_DIMENSIONS:
            raise ValueError("V1 multi-scope retrieval result dimensions must be 512.")
        return self
