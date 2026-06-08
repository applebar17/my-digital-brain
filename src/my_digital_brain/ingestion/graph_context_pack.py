from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from my_digital_brain.ingestion.contracts import (
    GraphContextDuplicateHintItem,
    GraphContextEntityItem,
    GraphContextKnownAliasItem,
    GraphContextPack,
    GraphContextRelationshipItem,
    GraphContextRelationshipSnippetItem,
    SourceRecordRef,
)


@dataclass(slots=True)
class WholeSourceGraphContextPackBuilder:
    """Build ingestion graph context from one whole-source hybrid retrieval call."""

    search_service: Any | None = None
    graph_service: Any | None = None
    limit: int = 10
    duplicate_hint_min_score: float = 0.75
    _aliases: dict[str, str] = field(default_factory=dict, init=False)
    _counter: int = field(default=0, init=False)

    def build(self, source: SourceRecordRef) -> GraphContextPack:
        self._aliases = {}
        self._counter = 0
        query = (source.raw_text or source.content_ref or "").strip()
        if not query:
            return GraphContextPack(
                source_id=source.source_id,
                retrieval_strategy="whole_source_hybrid",
                notes=["Source text was empty; graph context retrieval was skipped."],
            )
        if self.search_service is not None and hasattr(self.search_service, "search_hybrid"):
            return self._from_search_result(source, self.search_service.search_hybrid(
                query,
                limit=self.limit,
                include_history=True,
            ))
        if self.graph_service is not None and hasattr(self.graph_service, "search_nodes"):
            return self._from_graph_service_search(source, query)
        return GraphContextPack(
            source_id=source.source_id,
            retrieval_strategy="whole_source_hybrid",
            notes=["No graph search dependency configured for whole-source context retrieval."],
        )

    def _from_graph_service_search(
        self,
        source: SourceRecordRef,
        query: str,
    ) -> GraphContextPack:
        nodes = self.graph_service.search_nodes(query=query, limit=self.limit)
        entities = [self._entity_from_node(_serialize(node)) for node in nodes]
        return GraphContextPack(
            source_id=source.source_id,
            retrieval_strategy="whole_source_hybrid",
            compact_summary=_compact_summary(entities),
            entities=[entity for entity in entities if entity is not None],
        )

    def _from_search_result(self, source: SourceRecordRef, result: Any) -> GraphContextPack:
        payload = _serialize(result)
        hits = list(payload.get("hits") or [])
        graph_view = dict(payload.get("graph_view") or {})
        entities: list[GraphContextEntityItem] = []
        known_aliases: list[GraphContextKnownAliasItem] = []
        duplicate_hints: list[GraphContextDuplicateHintItem] = []

        for hit in hits[: self.limit]:
            entity = self._entity_from_hit(hit)
            if entity is None:
                continue
            entities.append(entity)
            known_aliases.extend(
                GraphContextKnownAliasItem(alias=alias, target_ref=entity.ref)
                for alias in entity.aliases
            )
            score = _float_or_none(hit.get("score"))
            if score is not None and score >= self.duplicate_hint_min_score:
                duplicate_hints.append(
                    GraphContextDuplicateHintItem(
                        candidate_text=entity.display_label,
                        possible_match_refs=[entity.ref],
                        reason="Whole-source hybrid retrieval found a strong existing target.",
                        score=score,
                    ),
                )

        relationships = [
            relationship
            for relationship in (
                self._relationship_from_graph_view(item)
                for item in list(graph_view.get("relationships") or [])[: self.limit]
            )
            if relationship is not None
        ]
        snippets = self._relationship_snippets(payload)
        return GraphContextPack(
            source_id=source.source_id,
            retrieval_strategy="whole_source_hybrid",
            compact_summary=_compact_summary(entities),
            known_aliases=_dedupe_alias_items(known_aliases),
            entities=entities,
            relationships=relationships,
            duplicate_hints=duplicate_hints,
            relationship_context_snippets=snippets,
        )

    def _entity_from_hit(self, hit: dict[str, Any]) -> GraphContextEntityItem | None:
        target = dict(hit.get("canonical_target") or hit.get("target") or {})
        target_id = (
            hit.get("canonical_target_id")
            or hit.get("primary_target_id")
            or target.get("id")
        )
        if not target_id:
            return None
        ref = self._alias(str(target_id), "NODE")
        label = hit.get("primary_target_label") or target.get("label")
        title = hit.get("title") or target.get("title") or str(target_id)
        description = hit.get("description") or target.get("description")
        aliases = _string_list(
            (target.get("display_metadata") or {}).get("aliases")
            or target.get("aliases")
        )
        return GraphContextEntityItem(
            ref=ref,
            display_label=str(title),
            entity_type=str(label) if label else None,
            compact_summary=str(description) if description else None,
            aliases=aliases,
            source_id=_first(hit.get("source_ids")),
            retrieval_strategy=str(hit.get("source") or "hybrid"),
            score=_float_or_none(hit.get("score")),
        )

    def _entity_from_node(self, node: dict[str, Any]) -> GraphContextEntityItem | None:
        properties = dict(node.get("properties") or {})
        node_id = properties.get("id")
        if not node_id:
            return None
        label = node.get("label")
        return GraphContextEntityItem(
            ref=self._alias(str(node_id), "NODE"),
            display_label=_display_title(properties, fallback=str(node_id)),
            entity_type=str(label) if label else None,
            compact_summary=_display_description(properties),
            aliases=_string_list(properties.get("aliases")),
        )

    def _relationship_from_graph_view(
        self,
        item: dict[str, Any],
    ) -> GraphContextRelationshipItem | None:
        rel_id = item.get("id") or item.get("relationship_id")
        from_id = item.get("from_id")
        to_id = item.get("to_id")
        if not (rel_id and from_id and to_id):
            return None
        return GraphContextRelationshipItem(
            ref=self._alias(str(rel_id), "REL"),
            from_ref=self._alias(str(from_id), "NODE"),
            to_ref=self._alias(str(to_id), "NODE"),
            relationship_type=item.get("type"),
            relationship_detail=item.get("description"),
            compact_summary=item.get("description"),
        )

    def _relationship_snippets(
        self,
        payload: dict[str, Any],
    ) -> list[GraphContextRelationshipSnippetItem]:
        snippets: list[GraphContextRelationshipSnippetItem] = []
        for package in list(payload.get("context_packages") or [])[: self.limit]:
            for collection_name in ("relationships", "relationship_contexts"):
                for item in list((package or {}).get(collection_name) or [])[: self.limit]:
                    summary = (
                        item.get("description")
                        or item.get("relationship_detail")
                        or item.get("title")
                        or item.get("text")
                    )
                    if not summary:
                        continue
                    ref = item.get("alias") or item.get("id") or f"SNIPPET_{len(snippets) + 1:06d}"
                    endpoint_refs = _string_list(
                        item.get("endpoint_refs")
                        or item.get("target_refs")
                        or [item.get("from_ref"), item.get("to_ref")]
                    )
                    snippets.append(
                        GraphContextRelationshipSnippetItem(
                            ref=str(ref),
                            endpoint_refs=endpoint_refs,
                            compact_summary=str(summary),
                        ),
                    )
        return snippets

    def _alias(self, raw_id: str, prefix: str) -> str:
        if raw_id.startswith(("NODE_", "REL_", "CLAIM_", "SOURCE_", "RELCTX_")):
            return raw_id
        existing = self._aliases.get(raw_id)
        if existing is not None:
            return existing
        self._counter += 1
        alias = f"{prefix}_{self._counter:06d}"
        self._aliases[raw_id] = alias
        return alias


def _serialize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value


def _display_title(properties: dict[str, Any], *, fallback: str) -> str:
    for key in ("display_name", "name", "title", "text", "description"):
        value = properties.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _display_description(properties: dict[str, Any]) -> str | None:
    for key in ("description", "emotional_summary", "original_user_words"):
        value = properties.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _first(value: Any) -> str | None:
    values = _string_list(value)
    return values[0] if values else None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _dedupe_alias_items(
    aliases: list[GraphContextKnownAliasItem],
) -> list[GraphContextKnownAliasItem]:
    seen: set[tuple[str, str | None]] = set()
    deduped: list[GraphContextKnownAliasItem] = []
    for item in aliases:
        key = (item.alias.casefold(), item.target_ref)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _compact_summary(entities: list[GraphContextEntityItem | None]) -> str | None:
    labels = [entity.display_label for entity in entities if entity is not None]
    if not labels:
        return None
    return "Retrieved graph context: " + ", ".join(labels[:6])
