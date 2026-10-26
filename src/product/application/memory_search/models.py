"""Typed contracts for owner-scoped deterministic memory search."""

from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MemorySearchFilterCriteriaDTO(BaseModel):
    """Storage-agnostic deterministic refinements shared by memory-search callers."""

    model_config = ConfigDict(extra="forbid")

    property_query: str | None = Field(
        default=None,
        description="Case-insensitive text matched against indexed graph properties.",
    )
    node_labels: list[str] = Field(
        default_factory=list,
        description="Canonical graph node labels allowed as deterministic search seeds.",
    )
    relationship_types: list[str] = Field(
        default_factory=list,
        description="Canonical relationship types retained in hydrated neighborhoods.",
    )
    from_time: str | None = Field(
        default=None,
        description="Optional inclusive ISO date or datetime applied to hydrated records.",
    )
    to_time: str | None = Field(
        default=None,
        description="Optional inclusive ISO date or datetime applied to hydrated records.",
    )

    @field_validator("property_query", "from_time", "to_time")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("node_labels", "relationship_types")
    @classmethod
    def _normalize_unique_values(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = value.strip()
            if item and item not in seen:
                seen.add(item)
                normalized.append(item)
        return normalized

    @model_validator(mode="after")
    def _validate_time_range(self) -> "MemorySearchFilterCriteriaDTO":
        parsed_from = self._parse_time(self.from_time, "from_time")
        parsed_to = self._parse_time(self.to_time, "to_time")
        if parsed_from is not None and parsed_to is not None and parsed_from > parsed_to:
            raise ValueError("from_time cannot be later than to_time.")
        return self

    @staticmethod
    def _parse_time(value: str | None, field_name: str) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{field_name} must be an ISO date or datetime string.") from error
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed

    def has_non_reference_seed_selector(self) -> bool:
        """Return whether these fields can identify seeds without an existing reference."""
        return bool(self.property_query or self.node_labels)


class MemorySearchFiltersDTO(MemorySearchFilterCriteriaDTO):
    """Internal search refinements containing only trusted backend identifiers."""

    seed_backend_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Backend graph IDs already resolved by trusted application code. "
            "Model-facing tools must resolve local references before constructing this request."
        ),
    )

    @field_validator("seed_backend_ids")
    @classmethod
    def _normalize_unique_backend_ids(cls, values: list[str]) -> list[str]:
        return cls._normalize_unique_values(values)

    def has_seed_selector(self) -> bool:
        """Return whether deterministic fields can identify initial graph seeds."""
        return bool(self.seed_backend_ids) or self.has_non_reference_seed_selector()


class MemorySearchRequestBaseDTO(BaseModel):
    """Bounded semantic and neighborhood parameters shared across search boundaries."""

    model_config = ConfigDict(extra="forbid")

    semantic_query: str | None = Field(
        default=None,
        description="Optional natural-language query used for vector similarity retrieval.",
    )
    neighborhood_depth: int = Field(
        default=1,
        ge=0,
        le=3,
        description="Graph degrees hydrated around selected seeds; zero returns seeds only.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum seeds and bounded hydrated nodes or relationships returned.",
    )

    @field_validator("semantic_query")
    @classmethod
    def _normalize_semantic_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class MemorySearchRequestDTO(MemorySearchRequestBaseDTO):
    """Internal request combining semantic retrieval and deterministic graph selection."""

    filters: MemorySearchFiltersDTO = Field(default_factory=MemorySearchFiltersDTO)

    @model_validator(mode="after")
    def _require_seed_selector(self) -> "MemorySearchRequestDTO":
        if self.semantic_query is None and not self.filters.has_seed_selector():
            raise ValueError(
                "Memory search requires a semantic query, property query, node label, "
                "or resolved seed reference. Relationship and time filters refine selected "
                "context but cannot identify a graph seed by themselves."
            )
        return self


class MemorySearchSeedDTO(BaseModel):
    """One ranked backend graph object selected for neighborhood hydration."""

    model_config = ConfigDict(extra="forbid")

    backend_id: str = Field(description="Backend graph identifier retained inside the application.")
    label: str = Field(description="Canonical graph node label.")
    title: str = Field(description="Human-readable graph-object title.")
    summary: str | None = Field(default=None, description="Concise available object description.")


class MemorySearchNodeDTO(MemorySearchSeedDTO):
    """Hydrated backend graph node prepared for later model-safe projection."""

    temporal_summary: str | None = Field(
        default=None,
        description="Normalized readable time associated with the node when available.",
    )


class MemorySearchRelationshipDTO(BaseModel):
    """Hydrated backend relationship with explicit endpoint identifiers."""

    model_config = ConfigDict(extra="forbid")

    backend_id: str = Field(description="Backend relationship identifier.")
    relationship_type: str = Field(description="Canonical graph relationship type.")
    from_backend_id: str = Field(description="Backend identifier of the source node.")
    to_backend_id: str = Field(description="Backend identifier of the destination node.")
    summary: str | None = Field(default=None, description="Readable relationship description.")
    temporal_summary: str | None = Field(
        default=None,
        description="Normalized readable time associated with the relationship when available.",
    )


class MemorySearchResultDTO(BaseModel):
    """Bounded internal graph context returned by deterministic memory search."""

    model_config = ConfigDict(extra="forbid")

    seed_backend_ids: list[str] = Field(
        default_factory=list,
        description="Ordered backend seed identifiers selected before hydration.",
    )
    nodes: list[MemorySearchNodeDTO] = Field(default_factory=list)
    relationships: list[MemorySearchRelationshipDTO] = Field(default_factory=list)
    truncated: bool = Field(
        default=False,
        description="Whether additional hydrated records existed beyond the requested limit.",
    )


class MemorySearchBackend(Protocol):
    """Owner-aware adapter over existing semantic and graph retrieval services."""

    def semantic_seeds(
        self,
        owner_id: str,
        query: str,
        *,
        filters: MemorySearchFiltersDTO,
        limit: int,
    ) -> list[MemorySearchSeedDTO]:
        """Return ranked graph seeds selected through existing semantic retrieval."""
        ...

    def deterministic_seeds(
        self,
        owner_id: str,
        filters: MemorySearchFiltersDTO,
        *,
        limit: int,
    ) -> list[MemorySearchSeedDTO]:
        """Return graph seeds selected through exact IDs or property filters."""
        ...

    def hydrate(
        self,
        owner_id: str,
        seed_backend_ids: list[str],
        *,
        filters: MemorySearchFiltersDTO,
        depth: int,
        limit: int,
    ) -> MemorySearchResultDTO:
        """Hydrate and filter one bounded graph neighborhood around selected seeds."""
        ...
