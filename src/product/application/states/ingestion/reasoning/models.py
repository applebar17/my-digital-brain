"""Structured semantic output of the ingestion reasoning state."""

from pydantic import BaseModel, ConfigDict, Field


class IngestionReasoningResultDTO(BaseModel):
    """Non-executable interpretation passed to later ingestion states."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str = Field(
        min_length=1,
        description="Concise interpretation of the memory-bearing conversation.",
    )
    clarification_points: list[str] = Field(
        default_factory=list,
        description=(
            "Unclear, incomplete, contradictory, or incoherent user statements that may "
            "materially affect later interpretation; each item also states why it matters."
        ),
    )
    entity_observations: list[str] = Field(
        default_factory=list,
        description="Relevant entity mentions and distinctions for candidate generation.",
    )
    alias_observations: list[str] = Field(
        default_factory=list,
        description="Possible aliases, nicknames, or mention variants needing later evaluation.",
    )
    relationship_observations: list[str] = Field(
        default_factory=list,
        description=(
            "Source-grounded relationship observations; co-presence alone is not a durable link."
        ),
    )
    episodic_details: list[str] = Field(
        default_factory=list,
        description=(
            "Details better retained as episodic memory rather than standalone durable objects."
        ),
    )
