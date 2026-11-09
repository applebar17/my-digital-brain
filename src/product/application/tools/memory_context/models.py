"""Model-facing contracts for MemoryLog and Perception creation tools."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from product.graph import MemoryLogKind


class MemoryContextObjectKind(StrEnum):
    """Object kinds created by the memory/context write state."""

    MEMORY_LOG = "memory_log"
    PERCEPTION = "perception"


class CreateMemoryLogDTO(BaseModel):
    """Explicit model-facing fields for one additive memory atom."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(
        min_length=1,
        max_length=120,
        description=(
            "Short distinctive user-facing title for one memory atom; never copy the "
            "whole memory text or use a reference as the title."
        ),
    )
    summary: str = Field(
        min_length=1,
        description="Compact self-contained account of this one observation or episode.",
    )
    log_kind: MemoryLogKind = Field(
        description="Functional memory category selected from the supported enum."
    )
    primary_host_ref: str = Field(
        description="Exact supplied node reference used as the primary timeline anchor."
    )
    involved_refs: list[str] = Field(
        description="Other supplied node references meaningfully involved in this memory."
    )
    happened_at: str | None = Field(
        description="User-stated or normalized occurrence time, or null when unavailable."
    )
    time_precision: str | None = Field(
        description="Readable timing precision or uncertainty, or null when unnecessary."
    )
    original_user_words: str | None = Field(
        description="Short exact user wording only when its phrasing carries meaning."
    )

    @model_validator(mode="after")
    def _validate_refs(self) -> "CreateMemoryLogDTO":
        if self.primary_host_ref in self.involved_refs:
            raise ValueError(
                "primary_host_ref is already the host and must not be repeated in involved_refs."
            )
        if len(self.involved_refs) != len(set(self.involved_refs)):
            raise ValueError("involved_refs must not repeat the same supplied reference.")
        return self


class CreatePerceptionDTO(BaseModel):
    """Explicit model-facing fields for one subjective perception."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_ref: str = Field(
        description="Exact supplied node reference for the object being perceived."
    )
    description: str = Field(
        min_length=1,
        description="Source-grounded subjective perception held by the owner.",
    )
    perception_type: str = Field(
        min_length=1,
        description="Concise category such as impression, feeling, mood, or preference.",
    )
    emotional_valence: str | None = Field(
        description="Readable emotional direction when supported, or null."
    )
    emotion_tags: list[str] = Field(
        description="Small source-grounded set of emotion labels; use an empty list if absent."
    )
    original_user_words: str | None = Field(
        description="Short exact user wording only when its phrasing carries meaning."
    )
    happened_at: str | None = Field(
        description="Known time associated with the perception, or null."
    )


class MemoryContextToolResultDTO(BaseModel):
    """One confirmed model-safe MemoryLog or Perception creation result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    object_kind: MemoryContextObjectKind
    object_ref: str = Field(description="Created model-facing reference for later steps.")
    title: str = Field(description="Concise readable title of the created object.")
    summary: str = Field(description="Concise description of the completed write.")
