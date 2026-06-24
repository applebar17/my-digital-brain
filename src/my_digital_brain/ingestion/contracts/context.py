from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import Field

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.ingestion.contracts.base import IngestionModel


class GraphContextRenderPurpose(StrEnum):
    REASONING = "reasoning"
    ENTITY_PLANNING = "entity_planning"
    RELATIONSHIP_PLANNING = "relationship_planning"
    MEMORY_LOG_PLANNING = "memory_log_planning"
    MEMORY_LOG_EXTRACTION = "memory_log_extraction"
    MISSING_ENTITY_PLANNING = "missing_entity_planning"
    ENTITY_EXTRACTION = "entity_extraction"
    RELATIONSHIP_EXTRACTION = "relationship_extraction"


class GraphContextKnownAliasItem(IngestionModel):
    alias: str = Field(description="Known user-facing alias, nickname, or mention text.")
    target_ref: str | None = Field(
        default=None,
        description="Backend alias or graph ref the alias may point to.",
    )
    label: str | None = Field(
        default=None,
        description="Optional display label for the referenced graph object.",
    )
    note: str | None = Field(
        default=None,
        description="Short context note explaining why this alias may matter.",
    )
    source_id: str | None = Field(
        default=None,
        description="Backend source id retained for traceability; renderers normally omit it.",
    )
    retrieval_strategy: str | None = Field(
        default=None,
        description="Backend retrieval strategy retained for audit; renderers normally omit it.",
    )


class GraphContextEntityItem(IngestionModel):
    ref: str = Field(description="Renderer-local or backend graph alias for this entity.")
    display_label: str = Field(description="Human-readable label for compact rendering.")
    entity_type: str | None = Field(
        default=None,
        description="Graph or LLM entity type when known.",
    )
    compact_summary: str | None = Field(
        default=None,
        description="Short semantic summary useful in LLM payloads.",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Known aliases as context hints, not identity definitions.",
    )
    relationship_refs: list[str] = Field(
        default_factory=list,
        description="Nearby relationship refs that a renderer may choose to include.",
    )
    source_id: str | None = Field(
        default=None,
        description="Backend source id retained for traceability; renderers normally omit it.",
    )
    retrieval_strategy: str | None = Field(
        default=None,
        description="Backend retrieval strategy retained for audit; renderers normally omit it.",
    )
    score: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional retrieval or similarity score for backend ranking.",
    )


class GraphContextRelationshipItem(IngestionModel):
    ref: str = Field(description="Renderer-local or backend graph alias for this relationship.")
    from_ref: str = Field(description="Source endpoint ref or alias.")
    to_ref: str = Field(description="Target endpoint ref or alias.")
    relationship_type: str | None = Field(
        default=None,
        description="Graph relationship type when known.",
    )
    relationship_kind: str | None = Field(
        default=None,
        description="Governed social relationship kind or semantic class when known.",
    )
    relationship_detail: str | None = Field(
        default=None,
        description="Source-grounded wording such as brother, roommate, or colleague.",
    )
    compact_summary: str | None = Field(
        default=None,
        description="Short relationship summary useful in LLM payloads.",
    )
    source_id: str | None = Field(
        default=None,
        description="Backend source id retained for traceability; renderers normally omit it.",
    )
    retrieval_strategy: str | None = Field(
        default=None,
        description="Backend retrieval strategy retained for audit; renderers normally omit it.",
    )
    score: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional retrieval or similarity score for backend ranking.",
    )


class GraphContextMemoryItem(IngestionModel):
    ref: str = Field(description="Renderer-local or backend memory ref.")
    compact_summary: str = Field(description="Short memory summary useful in LLM payloads.")
    related_refs: list[str] = Field(
        default_factory=list,
        description="Entity or relationship refs connected to this memory.",
    )
    source_id: str | None = Field(
        default=None,
        description="Backend source id retained for traceability; renderers normally omit it.",
    )
    retrieval_strategy: str | None = Field(
        default=None,
        description="Backend retrieval strategy retained for audit; renderers normally omit it.",
    )
    score: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional retrieval or similarity score for backend ranking.",
    )


class GraphContextDuplicateHintItem(IngestionModel):
    candidate_text: str = Field(description="New mention or candidate text being compared.")
    possible_match_refs: list[str] = Field(
        default_factory=list,
        description="Existing refs that may represent the same real-world object.",
    )
    reason: str = Field(description="Short reason why this may be a duplicate.")
    score: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional backend duplicate or similarity score.",
    )
    source_id: str | None = Field(
        default=None,
        description="Backend source id retained for traceability; renderers normally omit it.",
    )
    retrieval_strategy: str | None = Field(
        default=None,
        description="Backend retrieval strategy retained for audit; renderers normally omit it.",
    )


class GraphContextRelationshipSnippetItem(IngestionModel):
    ref: str = Field(description="Renderer-local relationship-context snippet ref.")
    endpoint_refs: list[str] = Field(
        default_factory=list,
        description="Endpoint refs or aliases mentioned by this snippet.",
    )
    compact_summary: str = Field(
        description="Short relationship-context snippet useful for planning or extraction.",
    )
    source_id: str | None = Field(
        default=None,
        description="Backend source id retained for traceability; renderers normally omit it.",
    )
    retrieval_strategy: str | None = Field(
        default=None,
        description="Backend retrieval strategy retained for audit; renderers normally omit it.",
    )


class GraphContextPack(IngestionModel):
    """Backend-owned graph context prepared for task-specific rendering."""

    context_pack_id: str = Field(
        default_factory=new_uuid,
        description="Backend correlation id for this graph context pack.",
    )
    compact_summary: str | None = Field(
        default=None,
        description="Optional backend-created context summary available to renderers.",
    )
    known_aliases: list[GraphContextKnownAliasItem] = Field(default_factory=list)
    entities: list[GraphContextEntityItem] = Field(default_factory=list)
    relationships: list[GraphContextRelationshipItem] = Field(default_factory=list)
    memories: list[GraphContextMemoryItem] = Field(default_factory=list)
    duplicate_hints: list[GraphContextDuplicateHintItem] = Field(default_factory=list)
    relationship_context_snippets: list[GraphContextRelationshipSnippetItem] = Field(
        default_factory=list,
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Backend notes that renderers may selectively expose.",
    )
    alias_map: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Backend alias-to-graph-id map retained for validation and write "
            "execution. Renderers normally omit it from LLM payloads."
        ),
    )
    source_id: str | None = Field(
        default=None,
        description=(
            "Backend source id for traceability. It must not be injected into LLM "
            "payloads unless a renderer explicitly needs it."
        ),
    )
    retrieval_strategy: str | None = Field(
        default=None,
        description=(
            "Backend retrieval strategy for traceability. It is normally excluded "
            "from rendered LLM payloads."
        ),
    )


class GraphContextPackView(IngestionModel):
    """LLM-friendly rendered view of a GraphContextPack."""

    purpose: GraphContextRenderPurpose = Field(
        description="Rendering purpose that selected this view's fields.",
    )
    compact_summary: str | None = Field(
        default=None,
        description="Task-relevant compact context summary.",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Rendered alias hints selected for this purpose.",
    )
    selected_entities: list[str] = Field(
        default_factory=list,
        description="Rendered entity snippets selected for this purpose.",
    )
    selected_relationships: list[str] = Field(
        default_factory=list,
        description="Rendered relationship snippets selected for this purpose.",
    )
    duplicate_hints: list[str] = Field(
        default_factory=list,
        description="Rendered duplicate hints selected for this purpose.",
    )
    relationship_context_snippets: list[str] = Field(
        default_factory=list,
        description="Rendered relationship-context snippets selected for this purpose.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Short task-relevant notes safe for an LLM payload.",
    )


class GraphContextPackRenderer(Protocol):
    """Future renderer service interface; no retrieval or runtime logic is implied."""

    def render(
        self,
        pack: GraphContextPack,
        purpose: GraphContextRenderPurpose,
    ) -> GraphContextPackView:
        """Return an LLM-friendly purpose-specific view of a backend context pack."""
