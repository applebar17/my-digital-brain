from __future__ import annotations

from pydantic import Field

from my_digital_brain.ingestion.contracts.base import IngestionModel


class TemporalScope(IngestionModel):
    valid_from: str | None = Field(
        default=None,
        description="Original or normalized lower bound for when the fact is valid.",
    )
    valid_to: str | None = Field(
        default=None,
        description="Original or normalized upper bound for when the fact is valid.",
    )
    resolved_start: str | None = Field(
        default=None,
        description="Deterministically queryable start time when a fuzzy date was resolved.",
    )
    resolved_end: str | None = Field(
        default=None,
        description="Deterministically queryable end time when a fuzzy date was resolved.",
    )
    time_precision: str | None = Field(
        default=None,
        description="Precision of the resolved time, such as day, month, year, or fuzzy.",
    )
    time_basis: str | None = Field(
        default=None,
        description="Reasoning basis for the time value, such as user stated or inferred.",
    )
    timezone: str | None = Field(
        default=None,
        description="Timezone used for resolved temporal values, when known.",
    )
    original_time_text: str | None = Field(
        default=None,
        description="Exact source wording for fuzzy or user-provided time references.",
    )


class AffectiveFields(IngestionModel):
    description: str | None = Field(
        default=None,
        description="Human-readable memory description, preserving emotional meaning.",
    )
    emotional_summary: str | None = Field(
        default=None,
        description="Concise summary of the emotional or perceptual weight of the memory.",
    )
    emotional_valence: str | None = Field(
        default=None,
        description="Qualitative emotional polarity, such as positive, negative, or mixed.",
    )
    emotional_intensity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional emotional intensity from 0 to 1 when explicitly inferable.",
    )
    emotion_tags: list[str] = Field(
        default_factory=list,
        description="Short emotion or perception tags that are useful for retrieval.",
    )
    original_user_words: str | None = Field(
        default=None,
        description="User wording worth preserving because it carries memory tone.",
    )
