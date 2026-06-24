from __future__ import annotations

from dataclasses import dataclass

from my_digital_brain.ingestion.contracts import (
    GraphContextDuplicateHintItem,
    GraphContextEntityItem,
    GraphContextKnownAliasItem,
    GraphContextMemoryItem,
    GraphContextPack,
    GraphContextPackView,
    GraphContextRelationshipItem,
    GraphContextRelationshipSnippetItem,
    GraphContextRenderPurpose,
)


@dataclass(slots=True)
class GraphContextPackRendererService:
    """Deterministic renderer for LLM-friendly graph context pack views."""

    max_aliases: int = 12
    max_entities: int = 8
    max_relationships: int = 8
    max_duplicate_hints: int = 6
    max_relationship_snippets: int = 6
    max_memories_as_notes: int = 4
    max_notes: int = 8

    def render(
        self,
        pack: GraphContextPack,
        purpose: GraphContextRenderPurpose,
    ) -> GraphContextPackView:
        purpose = GraphContextRenderPurpose(purpose)
        include_entities = purpose in {
            GraphContextRenderPurpose.REASONING,
            GraphContextRenderPurpose.ENTITY_PLANNING,
            GraphContextRenderPurpose.MISSING_ENTITY_PLANNING,
            GraphContextRenderPurpose.MEMORY_LOG_PLANNING,
            GraphContextRenderPurpose.MEMORY_LOG_EXTRACTION,
            GraphContextRenderPurpose.ENTITY_EXTRACTION,
            GraphContextRenderPurpose.RELATIONSHIP_PLANNING,
            GraphContextRenderPurpose.RELATIONSHIP_EXTRACTION,
        }
        include_relationships = purpose in {
            GraphContextRenderPurpose.REASONING,
            GraphContextRenderPurpose.MEMORY_LOG_PLANNING,
            GraphContextRenderPurpose.MEMORY_LOG_EXTRACTION,
            GraphContextRenderPurpose.RELATIONSHIP_PLANNING,
            GraphContextRenderPurpose.RELATIONSHIP_EXTRACTION,
        }
        include_duplicate_hints = purpose in {
            GraphContextRenderPurpose.REASONING,
            GraphContextRenderPurpose.ENTITY_PLANNING,
            GraphContextRenderPurpose.MISSING_ENTITY_PLANNING,
            GraphContextRenderPurpose.ENTITY_EXTRACTION,
        }
        include_relationship_snippets = purpose in {
            GraphContextRenderPurpose.REASONING,
            GraphContextRenderPurpose.MEMORY_LOG_PLANNING,
            GraphContextRenderPurpose.MEMORY_LOG_EXTRACTION,
            GraphContextRenderPurpose.RELATIONSHIP_PLANNING,
            GraphContextRenderPurpose.MISSING_ENTITY_PLANNING,
            GraphContextRenderPurpose.RELATIONSHIP_EXTRACTION,
        }

        notes = list(pack.notes[: self.max_notes])
        if purpose in {
            GraphContextRenderPurpose.REASONING,
            GraphContextRenderPurpose.MEMORY_LOG_PLANNING,
            GraphContextRenderPurpose.MEMORY_LOG_EXTRACTION,
        }:
            notes.extend(_memory_note(item) for item in pack.memories[: self.max_memories_as_notes])

        return GraphContextPackView(
            purpose=purpose,
            compact_summary=pack.compact_summary,
            aliases=[
                _render_alias(item)
                for item in pack.known_aliases[: self.max_aliases]
            ],
            selected_entities=(
                [
                    _render_entity(item)
                    for item in pack.entities[: self.max_entities]
                ]
                if include_entities
                else []
            ),
            selected_relationships=(
                [
                    _render_relationship(item)
                    for item in pack.relationships[: self.max_relationships]
                ]
                if include_relationships
                else []
            ),
            duplicate_hints=(
                [
                    _render_duplicate_hint(item)
                    for item in pack.duplicate_hints[: self.max_duplicate_hints]
                ]
                if include_duplicate_hints
                else []
            ),
            relationship_context_snippets=(
                [
                    _render_relationship_snippet(item)
                    for item in pack.relationship_context_snippets[
                        : self.max_relationship_snippets
                    ]
                ]
                if include_relationship_snippets
                else []
            ),
            notes=notes[: self.max_notes],
        )


def _render_alias(item: GraphContextKnownAliasItem) -> str:
    pieces = [item.alias]
    if item.label:
        pieces.append(f"-> {item.label}")
    if item.note:
        pieces.append(f"({item.note})")
    return " ".join(pieces)


def _render_entity(item: GraphContextEntityItem) -> str:
    label = item.display_label
    if item.entity_type:
        label = f"{label} [{item.entity_type}]"
    aliases = f" aliases: {', '.join(item.aliases)}" if item.aliases else ""
    summary = f" - {item.compact_summary}" if item.compact_summary else ""
    return f"{item.ref}: {label}{aliases}{summary}"


def _render_relationship(item: GraphContextRelationshipItem) -> str:
    relation = item.relationship_type or "relationship"
    detail_parts = [
        part
        for part in (item.relationship_kind, item.relationship_detail)
        if part
    ]
    details = f" ({'; '.join(detail_parts)})" if detail_parts else ""
    summary = f" - {item.compact_summary}" if item.compact_summary else ""
    return f"{item.ref}: {item.from_ref} -> {item.to_ref} [{relation}]{details}{summary}"


def _render_duplicate_hint(item: GraphContextDuplicateHintItem) -> str:
    matches = ", ".join(item.possible_match_refs) or "no specific match ref"
    score = f" score={item.score:.3g}" if item.score is not None else ""
    return f"{item.candidate_text}: possible match refs [{matches}] - {item.reason}{score}"


def _render_relationship_snippet(item: GraphContextRelationshipSnippetItem) -> str:
    endpoints = ", ".join(item.endpoint_refs) or "unspecified endpoints"
    return f"{item.ref}: endpoints [{endpoints}] - {item.compact_summary}"


def _memory_note(item: GraphContextMemoryItem) -> str:
    refs = f" refs: {', '.join(item.related_refs)}" if item.related_refs else ""
    return f"Memory {item.ref}: {item.compact_summary}{refs}"
