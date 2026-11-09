"""Typed backend contracts for relationship persistence and consumption."""

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RelationshipType(StrEnum):
    """Semantic direct relationships selectable by the relationship state."""

    PARTICIPATED_IN = "PARTICIPATED_IN"
    HAPPENED_AT = "HAPPENED_AT"
    KNOWS = "KNOWS"
    WORKS_AT = "WORKS_AT"
    OWNS = "OWNS"
    OWNED_BY = "OWNED_BY"
    CARED_FOR_BY = "CARED_FOR_BY"
    LIVES_WITH = "LIVES_WITH"
    MEMBER_OF = "MEMBER_OF"
    LOCATED_IN = "LOCATED_IN"
    RELATED_TO = "RELATED_TO"


class RelationshipContextCategory(StrEnum):
    """Stable categories used to identify narrative relationship contexts."""

    FAMILY = "family"
    FRIENDSHIP = "friendship"
    ROMANTIC = "romantic"
    PROFESSIONAL = "professional"
    COMMUNITY = "community"
    CAREGIVING = "caregiving"
    OWNERSHIP = "ownership"
    ATTACHMENT = "attachment"
    OTHER = "other"


class DirectRelationshipDTO(BaseModel):
    """Semantic properties of one durable graph relationship."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relationship_type: RelationshipType
    description: str | None = Field(
        description="Concise source-grounded meaning not already conveyed by the type."
    )
    relationship_detail: str | None = Field(
        description="Specific wording such as sibling, colleague, or organizer."
    )
    valid_from: str | None = Field(description="Known start of validity, or null.")
    valid_to: str | None = Field(description="Known end of validity, or null.")
    original_user_words: str | None = Field(
        description="Short original wording only when its phrasing matters."
    )


class DirectRelationshipPatchDTO(BaseModel):
    """Explicit non-destructive changes to one existing direct relationship."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str | None = Field(description="Replacement description, or null.")
    relationship_detail: str | None = Field(description="Replacement detail, or null.")
    valid_from: str | None = Field(description="Replacement validity start, or null.")
    valid_to: str | None = Field(description="Replacement validity end, or null.")
    original_user_words: str | None = Field(description="Replacement source wording, or null.")

    @model_validator(mode="after")
    def _require_change(self) -> "DirectRelationshipPatchDTO":
        if not self.model_dump(exclude_none=True):
            raise ValueError("A relationship update requires at least one changed field.")
        return self


class CreateRelationshipPersistenceDTO(BaseModel):
    """Backend-only direct-edge request after endpoint refs are resolved."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_backend_id: str
    to_backend_id: str
    relationship: DirectRelationshipDTO


class UpdateRelationshipPersistenceDTO(BaseModel):
    """Backend-only direct-edge update request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relationship_backend_id: str
    patch: DirectRelationshipPatchDTO


class StoredDirectRelationshipDTO(BaseModel):
    """Trusted persisted direct relationship and endpoint identities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend_id: str
    from_backend_id: str
    to_backend_id: str
    relationship: DirectRelationshipDTO
    created: bool = Field(description="Whether this operation created the edge.")


class RelationshipContextDTO(BaseModel):
    """Stable narrative properties of one relationship context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: RelationshipContextCategory
    description: str = Field(description="Stable narrative meaning of the relationship.")
    relationship_kind: str | None = Field(
        description="Specific supported wording such as sibling or university friend."
    )
    original_user_words: str | None = Field(
        description="Short original wording only when its phrasing carries meaning."
    )


class CreateRelationshipContextPersistenceDTO(BaseModel):
    """Backend-only context request after participant and memory refs resolve."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    participant_backend_ids: list[str] = Field(min_length=2)
    memory_log_backend_ids: list[str]
    context: RelationshipContextDTO


class StoredRelationshipContextDTO(BaseModel):
    """Persisted or reused relationship context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend_id: str
    participant_backend_ids: list[str]
    memory_log_backend_ids: list[str]
    context: RelationshipContextDTO
    created: bool


class RelationshipStateDTO(BaseModel):
    """One append-only time-qualified observation about a relationship context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str | None = Field(description="Relationship status at this point, or null.")
    closeness: str | None = Field(description="Source-grounded closeness, or null.")
    description: str | None = Field(description="Concise state description, or null.")
    emotional_summary: str | None = Field(description="Emotional meaning at this point, or null.")
    emotional_valence: str | None = Field(description="Emotional direction, or null.")
    emotion_tags: list[str] = Field(description="Source-grounded emotion labels.")
    original_user_words: str | None = Field(
        description="Short original wording only when its phrasing matters."
    )
    valid_from: str | None = Field(description="Known state start, or null.")
    valid_to: str | None = Field(description="Known state end, or null.")
    time_precision: str | None = Field(description="Known temporal precision, or null.")

    @model_validator(mode="after")
    def _require_meaningful_state(self) -> "RelationshipStateDTO":
        values = self.model_dump(exclude={"emotion_tags"}, exclude_none=True)
        if not values and not self.emotion_tags:
            raise ValueError(
                "A relationship state requires status, closeness, emotional, descriptive, "
                "or temporal information; do not create an empty initial state."
            )
        return self


class AppendRelationshipStatePersistenceDTO(BaseModel):
    """Backend-only state append request after context and memory refs resolve."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    context_backend_id: str
    memory_log_backend_ids: list[str]
    state: RelationshipStateDTO


class StoredRelationshipStateDTO(BaseModel):
    """Persisted or exact-reused relationship-state observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend_id: str
    context_backend_id: str
    memory_log_backend_ids: list[str]
    state: RelationshipStateDTO
    created: bool


class RelationshipContextDetailDTO(BaseModel):
    """Trusted bounded context detail returned for application projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relationship_context: StoredRelationshipContextDTO
    states: list[StoredRelationshipStateDTO]


class GraphRelationshipRepository(Protocol):
    """Owner-scoped relationship persistence and bounded read operations."""

    def create_or_get_relationship(
        self,
        owner_id: str,
        request: CreateRelationshipPersistenceDTO,
    ) -> StoredDirectRelationshipDTO: ...

    def update_relationship(
        self,
        owner_id: str,
        request: UpdateRelationshipPersistenceDTO,
    ) -> StoredDirectRelationshipDTO: ...

    def create_or_get_context(
        self,
        owner_id: str,
        request: CreateRelationshipContextPersistenceDTO,
    ) -> StoredRelationshipContextDTO: ...

    def append_state(
        self,
        owner_id: str,
        request: AppendRelationshipStatePersistenceDTO,
    ) -> StoredRelationshipStateDTO: ...

    def get_context_detail(
        self,
        owner_id: str,
        context_backend_id: str,
        *,
        state_limit: int,
    ) -> RelationshipContextDetailDTO: ...
