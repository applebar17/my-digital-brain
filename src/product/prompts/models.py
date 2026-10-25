"""Typed models for exact prompt selection and rendered prompt identity."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class PromptReferenceDTO(BaseModel):
    """Exact prompt template selected by application composition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_id: str = Field(
        min_length=1,
        description="Stable prompt identifier, such as 'conversation-entry'.",
    )
    version: str = Field(
        min_length=1,
        description="Exact template version to load; no implicit latest version is allowed.",
    )


class PromptRenderContextDTO(BaseModel):
    """Display-ready named values allowed to fill one prompt template."""

    model_config = ConfigDict(extra="forbid")

    values: dict[str, str] = Field(
        default_factory=dict,
        description="Named rendered strings keyed by the template placeholders they fill.",
    )


class PromptTemplateDTO(BaseModel):
    """One exact prompt template loaded from an injected source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: PromptReferenceDTO = Field(description="Exact identity of this template.")
    content: str = Field(min_length=1, description="Unrendered system-prompt template text.")


class PromptSnapshotDTO(BaseModel):
    """Stable identity of the template and rendered prompt used for one call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_id: str = Field(description="Stable prompt identifier.")
    version: str = Field(description="Exact selected prompt version.")
    template_checksum: str = Field(description="SHA-256 checksum of the template text.")
    rendered_checksum: str = Field(description="SHA-256 checksum of the rendered system prompt.")


class RenderedPromptDTO(BaseModel):
    """Resolved system prompt and the snapshot identifying how it was produced."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(min_length=1, description="Final system prompt supplied to the LLM call.")
    snapshot: PromptSnapshotDTO = Field(description="Version and checksums for this rendering.")


class PromptTemplateSource(Protocol):
    """Load one exact prompt version from local files, a database, or another store."""

    def load(self, reference: PromptReferenceDTO) -> PromptTemplateDTO:
        """Return the template matching the complete reference or raise a clear error."""
        ...
