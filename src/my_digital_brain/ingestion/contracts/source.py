from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from my_digital_brain.ingestion.contracts.base import IngestionModel
from my_digital_brain.ingestion.enums import SourceChannel, SourceType


class EvidenceRef(IngestionModel):
    source_id: str = Field(description="Source record that contains the supporting evidence.")
    extraction_run_id: str | None = Field(
        default=None,
        description="Extraction run that produced this evidence reference, when available.",
    )
    evidence_text: str | None = Field(
        default=None,
        description="Short verbatim or near-verbatim evidence snippet from the source.",
    )
    span_start: int | None = Field(
        default=None,
        ge=0,
        description="Character start offset in the source text, when known.",
    )
    span_end: int | None = Field(
        default=None,
        ge=0,
        description="Character end offset in the source text, when known.",
    )

    @model_validator(mode="after")
    def validate_span_order(self) -> EvidenceRef:
        if self.span_start is not None and self.span_end is not None:
            if self.span_end < self.span_start:
                raise ValueError("span_end must be greater than or equal to span_start")
        return self


class SourceRecordRef(IngestionModel):
    source_id: str = Field(description="Stable identifier for the source record.")
    source_type: SourceType = Field(description="Type of source being ingested.")
    channel: SourceChannel = Field(description="Transport or origin channel for the source.")
    external_id: str | None = Field(
        default=None,
        description="Provider-specific source identifier, such as a Telegram message id.",
    )
    content_ref: str | None = Field(
        default=None,
        description="Pointer to stored raw media or source content, when available.",
    )
    raw_text: str | None = Field(
        default=None,
        description="Text content to ingest, including transcribed audio when applicable.",
    )
    derived_from_source_id: str | None = Field(
        default=None,
        description="Parent source id when this source derives from media or another source.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Governed source metadata; avoid using this for frequently queried facts.",
    )


class ExtractionRunRef(IngestionModel):
    extraction_run_id: str = Field(description="Stable identifier for the extraction run.")
    source_id: str = Field(description="Source record processed by this extraction run.")
    processor: str = Field(description="Backend processor or service that ran extraction.")
    processor_version: str | None = Field(
        default=None,
        description="Version of the processor implementation.",
    )
    model: str | None = Field(default=None, description="AI model used, when applicable.")
    prompt_version: str | None = Field(
        default=None,
        description="Prompt version used, when applicable.",
    )
    schema_version: str | None = Field(
        default=None,
        description="Structured output schema version used, when applicable.",
    )
    status: str = Field(default="created", description="Operational status of the run.")
    metadata: dict[str, Any] = Field(default_factory=dict)
