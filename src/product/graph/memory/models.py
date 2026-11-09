"""Typed backend contracts for memory-log and perception persistence."""

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class MemoryLogKind(StrEnum):
    """Compact functional categories used to retrieve and render memory atoms."""

    OBSERVATION = "observation"
    EPISODE = "episode"
    UPDATE = "update"
    PREFERENCE = "preference"
    RELATIONSHIP_NOTE = "relationship_note"
    EVENT_DETAIL = "event_detail"
    OTHER = "other"


class MemoryLogWriteDTO(BaseModel):
    """Trusted MemoryLog payload after model-facing references are resolved."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(description="Concise user-facing title for the memory atom.")
    summary: str = Field(description="Compact self-contained content of the memory atom.")
    log_kind: MemoryLogKind = Field(description="Functional category of the memory atom.")
    primary_host_backend_id: str = Field(
        description="Resolved backend identifier of the primary timeline host."
    )
    involved_backend_ids: list[str] = Field(
        description="Resolved backend identifiers of other meaningful participants."
    )
    happened_at: str | None = Field(
        description="User-stated or normalized time when the memory occurred."
    )
    time_precision: str | None = Field(
        description="Available precision or uncertainty of happened_at."
    )
    original_user_words: str | None = Field(
        description="Short original wording retained only when its phrasing matters."
    )


class PerceptionDTO(BaseModel):
    """Typed properties persisted on one Perception object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str = Field(description="The owner's source-grounded subjective perception.")
    perception_type: str = Field(
        description="Concise category such as impression, feeling, mood, or preference."
    )
    emotional_valence: str | None = Field(
        description="Readable emotional direction when explicitly supported."
    )
    emotion_tags: list[str] = Field(
        description="Small source-grounded set of useful emotion labels."
    )
    original_user_words: str | None = Field(
        description="Short original wording retained when its phrasing carries meaning."
    )
    happened_at: str | None = Field(
        description="Known time associated with this perception, when available."
    )


class CreatePerceptionPersistenceDTO(BaseModel):
    """Backend-only request after the model-facing target ref is resolved."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_backend_id: str = Field(
        description="Resolved backend identifier used only to attach the perception."
    )
    perception: PerceptionDTO = Field(
        description="Typed properties to persist on the Perception object."
    )


class StoredMemoryLogDTO(BaseModel):
    """Persisted MemoryLog returned across the trusted repository boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend_id: str
    memory_log: MemoryLogWriteDTO


class StoredPerceptionDTO(BaseModel):
    """Persisted Perception returned across the trusted repository boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend_id: str
    perception: PerceptionDTO


class GraphMemoryRepository(Protocol):
    """Owner-scoped persistence operations required by MemoryContextWriteState."""

    def create_memory_log(
        self,
        owner_id: str,
        memory_log: MemoryLogWriteDTO,
    ) -> StoredMemoryLogDTO: ...

    def create_perception(
        self,
        owner_id: str,
        request: CreatePerceptionPersistenceDTO,
    ) -> StoredPerceptionDTO: ...
