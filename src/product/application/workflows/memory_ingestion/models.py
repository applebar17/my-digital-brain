"""Typed entry and preparation contracts for the memory-ingestion workflow."""

from pydantic import BaseModel, ConfigDict, Field

from product.application.references import OwnerContextDTO, ReferenceEntryDTO
from product.application.tools.memory_search import MemorySearchToolResultDTO


class IngestMemoryRequestDTO(BaseModel):
    """Optional purpose guidance supplied by the invoking conversation model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    guidance: str | None = Field(
        default=None,
        description=(
            "Optional concise guidance about what to retain. The source content is inherited "
            "from conversation history and must not be copied into this field."
        ),
    )


class IngestionOwnerIdentityDTO(BaseModel):
    """Backend-bound owner identity used to build the safe model projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend_id: str = Field(description="Persisted owner identity kept outside model context.")
    name: str | None = Field(default=None, description="Safely available owner given name.")
    surname: str | None = Field(default=None, description="Safely available owner surname.")


class IngestionPreparedContextDTO(BaseModel):
    """Model-safe owner, references, and bounded context prepared before reasoning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: IngestMemoryRequestDTO
    owner: OwnerContextDTO
    known_references: list[ReferenceEntryDTO] = Field(default_factory=list)
    retrieved_memory: MemorySearchToolResultDTO = Field(
        default_factory=MemorySearchToolResultDTO
    )
