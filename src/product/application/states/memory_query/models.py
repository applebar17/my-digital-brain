"""Typed request, context, and result contracts for grounded memory queries."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from product.application.tools.memory_search.models import MemorySearchToolResultDTO


class MemoryQueryRequestDTO(BaseModel):
    """A user memory question or need to investigate using grounded context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    goal: str = Field(
        min_length=1,
        description="Complete memory question, doubt, or need that the state must resolve.",
    )

    @field_validator("goal")
    @classmethod
    def _normalize_goal(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Memory query goal must not be empty.")
        return normalized


class MemoryQueryContextPacket(BaseModel):
    """Initial model-safe search context prepared before the main LLM session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    initial_search: MemorySearchToolResultDTO = Field(
        description="Bounded result of the deterministic initial semantic search."
    )
    initial_search_error: str | None = Field(
        default=None,
        description="Safe recoverable search error supplied when initial retrieval failed.",
    )


class MemoryQueryFactDTO(BaseModel):
    """One concise grounded fact and the active references supporting it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str = Field(
        min_length=1,
        description="Concise fact supported by the retrieved memory context.",
    )
    refs: list[str] = Field(
        default_factory=list,
        description="Active object or relationship references directly supporting this fact.",
    )


class MemoryQueryResultDTO(BaseModel):
    """Compact grounded result returned to a direct caller or parent AI state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str = Field(
        min_length=1,
        description="Concise answer grounded only in the retrieved memory context.",
    )
    supporting_facts: list[MemoryQueryFactDTO] = Field(
        default_factory=list,
        description="Important grounded facts used to produce the answer.",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="Relevant missing, ambiguous, or weakly supported information.",
    )
