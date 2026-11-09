"""Model-facing actions and results for relationship writing."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from product.graph import RelationshipContextCategory, RelationshipType


class CreateDirectRelationshipActionDTO(BaseModel):
    """Create or exact-reuse one durable semantic edge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["create_direct"]
    relationship_type: RelationshipType
    from_ref: str = Field(description="Exact supplied source node reference.")
    to_ref: str = Field(description="Exact supplied target node reference.")
    description: str | None = Field(description="Concise grounded meaning, or null.")
    relationship_detail: str | None = Field(
        description="Specific wording such as sibling or colleague, or null."
    )
    valid_from: str | None = Field(description="Known validity start, or null.")
    valid_to: str | None = Field(description="Known validity end, or null.")
    original_user_words: str | None = Field(
        description="Short original wording only when its phrasing matters."
    )

    @model_validator(mode="after")
    def _different_endpoints(self) -> "CreateDirectRelationshipActionDTO":
        if self.from_ref == self.to_ref:
            raise ValueError("A direct relationship requires two different node references.")
        return self


class UpdateDirectRelationshipActionDTO(BaseModel):
    """Explicitly enrich one supplied direct relationship."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["update_direct"]
    relationship_ref: str = Field(
        description="Exact supplied reference of the existing direct relationship."
    )
    description: str | None = Field(description="Replacement description, or null.")
    relationship_detail: str | None = Field(description="Replacement detail, or null.")
    valid_from: str | None = Field(description="Replacement validity start, or null.")
    valid_to: str | None = Field(description="Replacement validity end, or null.")
    original_user_words: str | None = Field(description="Replacement source wording, or null.")


class CreateOrReuseRelationshipContextActionDTO(BaseModel):
    """Create or exact-reuse one narrative context for resolved participants."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["create_or_reuse_context"]
    participant_refs: list[str] = Field(
        min_length=2,
        description="Distinct supplied node refs participating in this relationship context."
    )
    category: RelationshipContextCategory
    description: str = Field(description="Stable narrative meaning of the relationship.")
    relationship_kind: str | None = Field(
        description="Specific wording such as sibling or university friend, or null."
    )
    original_user_words: str | None = Field(
        description="Short original wording only when its phrasing matters."
    )
    memory_refs: list[str] = Field(
        description="Created MemoryLog refs that support or update this context."
    )

    @model_validator(mode="after")
    def _distinct_participants(self) -> "CreateOrReuseRelationshipContextActionDTO":
        if len(self.participant_refs) != len(set(self.participant_refs)):
            raise ValueError("participant_refs must contain each node reference only once.")
        return self


class AppendRelationshipStateActionDTO(BaseModel):
    """Append one meaningful time-qualified state to a supplied context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["append_state"]
    context_ref: str = Field(description="Exact supplied RelationshipContext reference.")
    status: str | None = Field(description="Relationship status at this point, or null.")
    closeness: str | None = Field(description="Source-grounded closeness, or null.")
    description: str | None = Field(description="Concise state description, or null.")
    emotional_summary: str | None = Field(description="Emotional meaning, or null.")
    emotional_valence: str | None = Field(description="Emotional direction, or null.")
    emotion_tags: list[str] = Field(description="Source-grounded emotion labels.")
    original_user_words: str | None = Field(
        description="Short original wording only when its phrasing matters."
    )
    valid_from: str | None = Field(description="Known state start, or null.")
    valid_to: str | None = Field(description="Known state end, or null.")
    time_precision: str | None = Field(description="Known temporal precision, or null.")
    memory_refs: list[str] = Field(
        description="Created MemoryLog refs supporting this state observation."
    )


RelationshipAction = Annotated[
    CreateDirectRelationshipActionDTO
    | UpdateDirectRelationshipActionDTO
    | CreateOrReuseRelationshipContextActionDTO
    | AppendRelationshipStateActionDTO,
    Field(discriminator="operation"),
]


class RelationshipActionRequestDTO(BaseModel):
    """One explicit semantic relationship operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: RelationshipAction


class RelationshipObjectKind(StrEnum):
    """Model-safe object kinds returned by the relationship tool."""

    DIRECT_RELATIONSHIP = "direct_relationship"
    RELATIONSHIP_CONTEXT = "relationship_context"
    RELATIONSHIP_STATE = "relationship_state"


class RelationshipWriteOutcome(StrEnum):
    """Applied persistence outcome for one relationship action."""

    CREATED = "created"
    REUSED = "reused"
    UPDATED = "updated"


class RelationshipToolResultDTO(BaseModel):
    """One confirmed model-facing relationship write result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    object_kind: RelationshipObjectKind
    outcome: RelationshipWriteOutcome
    object_ref: str = Field(description="Created, reused, or updated local reference.")
    title: str = Field(description="Concise readable relationship title.")
    summary: str = Field(description="Concise description of the confirmed operation.")
