"""Typed contracts for run-scoped model references and private bindings."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReferenceObjectKind(StrEnum):
    """Object categories represented in a workflow reference context."""

    NODE = "node"
    MEMORY_LOG = "memory_log"
    RELATIONSHIP = "relationship"
    CONTEXT = "context"
    MEDIA = "media"
    CANDIDATE = "candidate"


class ReferenceResolutionStatus(StrEnum):
    """Lifecycle position of a referenced object in the active workflow."""

    EXISTING = "existing"
    PROPOSED = "proposed"
    CREATED = "created"


class ReferenceEntryDTO(BaseModel):
    """One model-safe object reference available in the current workflow."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: str = Field(
        min_length=1,
        description=(
            "Backend-issued model-facing reference for this active workflow. "
            "Use this exact value when another DTO or tool requires the object."
        ),
    )
    object_kind: ReferenceObjectKind = Field(
        description="Domain object category represented by this reference."
    )
    label: str | None = Field(
        default=None,
        description="Graph label or domain type when it helps identify the object.",
    )
    display_name: str | None = Field(
        default=None,
        description="Readable object name when one is available.",
    )
    summary: str | None = Field(
        default=None,
        description="Brief user-meaningful description when a name alone is insufficient.",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Known useful alternate names; excludes speculative aliases.",
    )
    resolution_status: ReferenceResolutionStatus = Field(
        description="Whether the object is existing, proposed, or created in this workflow."
    )


class OwnerContextDTO(BaseModel):
    """The active workflow owner's safe identity projection for an LLM context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(
        min_length=1,
        description=(
            "Readable model-facing owner reference derived from safe name information, "
            "or 'owner' when a full name is unavailable. It is not a backend identifier."
        ),
    )
    name: str | None = Field(default=None, description="Owner's safely available given name.")
    surname: str | None = Field(default=None, description="Owner's safely available surname.")


class ReferenceBindingDTO(BaseModel):
    """Private backend binding transported only between trusted application components."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: str = Field(min_length=1, description="Model-facing reference being bound.")
    backend_id: str = Field(
        min_length=1,
        description="Persisted identifier kept outside every model-facing projection.",
    )


class ReferenceContextDeltaDTO(BaseModel):
    """Typed reference additions or updates returned by a child state or workflow."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entries: list[ReferenceEntryDTO] = Field(default_factory=list)
    bindings: list[ReferenceBindingDTO] = Field(
        default_factory=list,
        description="Private bindings merged by trusted application composition only.",
    )
