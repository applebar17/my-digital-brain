"""Typed input and output contracts for memory/context writing."""

from pydantic import BaseModel, ConfigDict, Field

from product.application.references import OwnerContextDTO, ReferenceEntryDTO
from product.application.states.ingestion.node_resolution import NodeResolutionStateResultDTO
from product.application.states.ingestion.reasoning import IngestionReasoningResultDTO
from product.application.tools.memory_context import MemoryContextToolResultDTO


class MemoryContextWriteInputDTO(BaseModel):
    """Resolved context required to create memory atoms and perceptions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reasoning: IngestionReasoningResultDTO = Field(
        description="Completed ingestion interpretation grounding memory extraction."
    )
    node_resolution_results: list[NodeResolutionStateResultDTO] = Field(
        description="Completed node-resolution batches available to the memory state."
    )
    owner: OwnerContextDTO = Field(description="Safe projection of the current memory owner.")
    references: list[ReferenceEntryDTO] = Field(
        description="Current model-facing refs, including every resolved node target."
    )


class MemoryContextWriteResultDTO(BaseModel):
    """Confirmed writes and honest deferrals returned to relationship work."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    writes: list[MemoryContextToolResultDTO] = Field(
        description="Only MemoryLog or Perception writes confirmed by tool outputs."
    )
    deferred_items: list[str] = Field(
        description="Memory or perception items not written, with a concise reason."
    )
    summary: str = Field(description="Concise account of what this state preserved.")
