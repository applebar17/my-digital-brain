"""Model-facing contracts for the reusable read-only memory-search tool."""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from product.application.memory_search.models import (
    MemorySearchFilterCriteriaDTO,
    MemorySearchRequestBaseDTO,
)
from product.application.references.models import ReferenceEntryDTO


class MemorySearchToolFiltersDTO(MemorySearchFilterCriteriaDTO):
    """Readable deterministic filters accepted from an LLM tool call."""

    seed_refs: list[str] = Field(
        default_factory=list,
        description=(
            "Exact active references for existing graph objects that should seed the search. "
            "Use only references supplied in the current context; never provide database IDs."
        ),
    )

    @field_validator("seed_refs")
    @classmethod
    def _normalize_unique_refs(cls, values: list[str]) -> list[str]:
        return cls._normalize_unique_values(values)

    def has_seed_selector(self) -> bool:
        """Return whether deterministic model-facing fields can identify initial seeds."""
        return bool(self.seed_refs) or self.has_non_reference_seed_selector()


class MemorySearchToolInputDTO(MemorySearchRequestBaseDTO):
    """One bounded model request for semantic or deterministic memory retrieval."""

    filters: MemorySearchToolFiltersDTO = Field(default_factory=MemorySearchToolFiltersDTO)

    @model_validator(mode="after")
    def _require_seed_selector(self) -> "MemorySearchToolInputDTO":
        if self.semantic_query is None and not self.filters.has_seed_selector():
            raise ValueError(
                "Memory search requires a semantic query, property query, node label, "
                "or active seed reference. Relationship and time filters only refine results."
            )
        return self


class MemorySearchObjectDTO(ReferenceEntryDTO):
    """One hydrated graph object projected through the active reference context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    temporal_summary: str | None = Field(
        default=None,
        description="Readable time associated with this object when it is relevant and known.",
    )


class MemorySearchToolRelationshipDTO(ReferenceEntryDTO):
    """One hydrated relationship whose endpoints use active model-facing references."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_ref: str = Field(
        min_length=1,
        description="Active reference for the relationship's source object.",
    )
    to_ref: str = Field(
        min_length=1,
        description="Active reference for the relationship's destination object.",
    )
    temporal_summary: str | None = Field(
        default=None,
        description="Readable time associated with this relationship when known.",
    )


class MemorySearchToolResultDTO(BaseModel):
    """Bounded model-safe context returned by one deterministic memory search."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed_refs: list[str] = Field(
        default_factory=list,
        description="Active references selected as the starting points for hydration.",
    )
    objects: list[MemorySearchObjectDTO] = Field(
        default_factory=list,
        description="Hydrated model-safe graph objects in deterministic result order.",
    )
    relationships: list[MemorySearchToolRelationshipDTO] = Field(
        default_factory=list,
        description="Hydrated relationships whose endpoints refer to returned active refs.",
    )
    truncated: bool = Field(
        default=False,
        description="Whether more matching context existed beyond the requested bound.",
    )
