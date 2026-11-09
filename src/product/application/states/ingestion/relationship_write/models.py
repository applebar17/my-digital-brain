"""Typed input and output contracts for relationship writing."""

from pydantic import BaseModel, ConfigDict, Field

from product.application.references import OwnerContextDTO, ReferenceEntryDTO
from product.application.states.ingestion.memory_context import MemoryContextWriteResultDTO
from product.application.states.ingestion.node_resolution import NodeResolutionStateResultDTO
from product.application.states.ingestion.reasoning import IngestionReasoningResultDTO
from product.application.tools.relationship_write import RelationshipToolResultDTO


class RelationshipWriteInputDTO(BaseModel):
    """Resolved objects and prior outcomes required for relationship decisions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reasoning: IngestionReasoningResultDTO
    node_resolution_results: list[NodeResolutionStateResultDTO]
    memory_context_result: MemoryContextWriteResultDTO
    owner: OwnerContextDTO
    references: list[ReferenceEntryDTO]


class RelationshipWriteResultDTO(BaseModel):
    """Confirmed relationship writes and honest deferred observations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    writes: list[RelationshipToolResultDTO] = Field(
        description="Only direct, context, or state writes confirmed by tool outputs."
    )
    deferred_relationships: list[str] = Field(
        description="Relationship observations not written, with a concise reason."
    )
    summary: str = Field(description="Concise account of the relationship work completed.")
