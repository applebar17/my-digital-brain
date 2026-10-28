"""Temporary ingestion-tool contracts retained by conversation entry."""

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field

from product.application.workflows.memory_ingestion.models import IngestMemoryRequestDTO


class IngestMemoryResultDTO(BaseModel):
    """Temporary ingestion result interpreted by the conversation-entry state."""

    model_config = ConfigDict(extra="forbid")

    result: str = Field(
        min_length=1,
        description="Readable capability result for the invoking conversation agent to interpret.",
    )


IngestMemoryHandler = Callable[[IngestMemoryRequestDTO], IngestMemoryResultDTO]
