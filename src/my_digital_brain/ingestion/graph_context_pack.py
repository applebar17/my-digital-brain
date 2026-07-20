from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from my_digital_brain.core.ids import new_uuid
from my_digital_brain.core.owner_context import OwnerSnapshot
from my_digital_brain.ingestion.contracts import (
    GraphContextDuplicateHintItem,
    GraphContextEntityItem,
    GraphContextKnownAliasItem,
    GraphContextPack,
    GraphContextRelationshipItem,
    GraphContextRelationshipSnippetItem,
    ReferenceObjectKind,
    SourceRecordRef,
)
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry


@dataclass(slots=True)
class WholeSourceGraphContextPackBuilder:
    """Build ingestion graph context from one whole-source hybrid retrieval call."""

    search_service: Any | None = None
    graph_service: Any | None = None
    owner_graph_node_id: str | None = None
    limit: int = 10
    duplicate_hint_min_score: float = 0.75

    def build(self, source: SourceRecordRef) -> GraphContextPack:
        registry = RunReferenceRegistry(
            graph_scope=str(source.metadata.get("graph_scope") or "default"),
            run_scope=str(source.metadata.get("ingestion_run_id") or new_uuid()),
        )
        owner_id = _owner_id(source, self.owner_graph_node_id)
        if owner_id:
            registry.register_owner(owner_id)
        query = (source.raw_text or source.content_ref or "").strip()
        owner_snapshot = self._owner_snapshot(source)
        if not query:
            return GraphContextPack(
                source_id=source.source_id,
                retrieval_strategy="whole_source_hybrid",
                notes=["Source text was empty; graph context retrieval was skipped."],
                alias_map=registry.backend_alias_map(),
                reference_registry_snapshot=registry.snapshot(),
                owner_snapshot=owner_snapshot,
            )
        if self.search_service is not None and hasattr(self.search_service, "search_hybrid"):
            return self._from_search_result(
                source,
                self.search_service.search_hybrid(query, limit=self.limit, include_history=True),
                registry,
            )
        if self.graph_service is not None and hasattr(self.graph_service, "search_nodes"):
            return self._from_graph_service_search(source, query, registry)
        return GraphContextPack(
            source_id=source.source_id,
            retrieval_strategy="whole_source_hybrid",
            notes=["No graph search dependency configured for whole-source context retrieval."],
            alias_map=registry.backend_alias_map(),
            reference_registry_snapshot=registry.snapshot(),
            owner_snapshot=owner_snapshot,
        )

    def _from_graph_service_search(
        self,
        source: SourceRecordRef,
        query: str,
        registry: RunReferenceRegistry,
    ) -> GraphContextPack:
        owner_snapshot = self._owner_snapshot(source)
        nodes = self.graph_service.search_nodes(query=query, limit=self.limit)
        entities = [
            self._entity_from_node(_serialize(node), registry)
            for node in nodes
        ]
        return GraphContextPack(
            source_id=source.source_id,
            retrieval_strategy="whole_source_hybrid",
            compact_summary=_compact_summary(entities),
            entities=[entity for entity in entities if entity is not None],
            alias_map=registry.backend_alias_map(),
            reference_registry_snapshot=registry.snapshot(),
            owner_snapshot=owner_snapshot,
        )

    def _from_search_result(
        self,
        source: SourceRecordRef,
        result: Any,
        registry: RunReferenceRegistry,
    ) -> GraphContextPack:
        owner_snapshot = self._owner_snapshot(source)
        payload = _serialize(result)
        hits = list(payload.get("hits") or [])
        graph_view = dict(payload.get("graph_view") or {})
        entities: list[GraphContextEntityItem] = []
        known_aliases: list[GraphContextKnownAliasItem] = []
        duplicate_hints: list[GraphContextDuplicateHintItem] = []

        for hit in hits[: self.limit]:
            entity = self._entity_from_hit(hit, registry)
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
                self._relationship_from_graph_view(item, registry)
                for item in list(graph_view.get("relationships") or [])[: self.limit]
            )
            if relationship is not None
        ]
        snippets = self._relationship_snippets(payload, registry)
        return GraphContextPack(
            source_id=source.source_id,
            retrieval_strategy="whole_source_hybrid",
            compact_summary=_compact_summary(entities),
            known_aliases=_dedupe_alias_items(known_aliases),
            entities=entities,
            relationships=relationships,
            duplicate_hints=duplicate_hints,
            relationship_context_snippets=snippets,
            alias_map=registry.backend_alias_map(),
            reference_registry_snapshot=registry.snapshot(),
            owner_snapshot=owner_snapshot,
        )

    def _owner_snapshot(self, source: SourceRecordRef) -> OwnerSnapshot | None:
        owner_id = _owner_id(source, self.owner_graph_node_id)
        if not owner_id:
            return None
        if self.graph_service is not None and hasattr(self.graph_service, "get_node"):
            try:
                node = self.graph_service.get_node(owner_id)
                properties = getattr(node, "properties", None)
                if isinstance(properties, dict):
                    return OwnerSnapshot.from_properties(properties)
            except Exception:
                pass
        return OwnerSnapshot()

    def _entity_from_hit(
        self,
        hit: dict[str, Any],
        registry: RunReferenceRegistry,
    ) -> GraphContextEntityItem | None:
        target = dict(hit.get("canonical_target") or hit.get("target") or {})
        target_id = (
            hit.get("canonical_target_id")
            or hit.get("primary_target_id")
            or target.get("id")
        )
        if not target_id:
            return None
        label = hit.get("primary_target_label") or target.get("label")
        title = hit.get("title") or target.get("title") or str(target_id)
        description = hit.get("description") or target.get("description")
        aliases = _string_list(
            (target.get("display_metadata") or {}).get("aliases")
            or target.get("aliases")
        )
        ref = registry.register_existing(
            str(target_id),
            object_kind=ReferenceObjectKind.NODE,
            label=str(label or "Node"),
            display_label=str(title),
            aliases=aliases,
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

    def _entity_from_node(
        self,
        node: dict[str, Any],
        registry: RunReferenceRegistry,
    ) -> GraphContextEntityItem | None:
        properties = dict(node.get("properties") or {})
        node_id = properties.get("id")
        if not node_id:
            return None
        label = node.get("label")
        ref = registry.register_existing(
            str(node_id),
            object_kind=ReferenceObjectKind.NODE,
            label=str(label or "Node"),
            display_label=_display_title(properties, fallback=str(node_id)),
            aliases=_string_list(properties.get("aliases")),
        )
        return GraphContextEntityItem(
            ref=ref,
            display_label=_display_title(properties, fallback=str(node_id)),
            entity_type=str(label) if label else None,
            compact_summary=_display_description(properties),
            aliases=_string_list(properties.get("aliases")),
        )

    def _relationship_from_graph_view(
        self,
        item: dict[str, Any],
        registry: RunReferenceRegistry,
    ) -> GraphContextRelationshipItem | None:
        rel_id = item.get("id") or item.get("relationship_id")
        from_id = item.get("from_id")
        to_id = item.get("to_id")
        if not (rel_id and from_id and to_id):
            return None
        from_ref = _node_ref(str(from_id), registry)
        to_ref = _node_ref(str(to_id), registry)
        rel_ref = registry.register_existing(
            str(rel_id),
            object_kind=ReferenceObjectKind.EDGE,
            label=str(item.get("type") or "Relationship"),
            display_label=str(item.get("description") or item.get("type") or "Relationship"),
        )
        return GraphContextRelationshipItem(
            ref=rel_ref,
            from_ref=from_ref,
            to_ref=to_ref,
            relationship_type=item.get("type"),
            relationship_detail=item.get("description"),
            compact_summary=item.get("description"),
        )

    def _relationship_snippets(
        self,
        payload: dict[str, Any],
        registry: RunReferenceRegistry,
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
                    item_id = item.get("id") or item.get("relationship_context_id")
                    ref = (
                        registry.register_existing(
                            str(item_id),
                            object_kind=ReferenceObjectKind.CONTEXT,
                            label="RelationshipContext",
                            display_label=str(summary),
                        )
                        if item_id
                        else registry.register_local(
                            object_kind=ReferenceObjectKind.CONTEXT,
                            label="RelationshipContext",
                            display_label=str(summary),
                        )
                    )
                    endpoint_refs = _string_list(
                        item.get("endpoint_refs")
                        or item.get("target_refs")
                        or [item.get("from_ref"), item.get("to_ref")]
                    )
                    snippets.append(
                        GraphContextRelationshipSnippetItem(
                            ref=str(ref),
                            endpoint_refs=[
                                _node_ref(endpoint_ref, registry)
                                for endpoint_ref in endpoint_refs
                            ],
                            compact_summary=str(summary),
                        ),
                    )
        return snippets


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


def _owner_id(
    source: SourceRecordRef,
    canonical_owner_id: str | None = None,
) -> str | None:
    if canonical_owner_id:
        return str(canonical_owner_id)
    return (
        source.metadata.get("owner_graph_node_id")
        or source.metadata.get("owner_node_id")
        or source.metadata.get("owner_id")
    )


def _node_ref(raw_ref: str, registry: RunReferenceRegistry) -> str:
    if raw_ref == "OWNER":
        registry.resolve(raw_ref, expected_kind=ReferenceObjectKind.NODE)
        return raw_ref
    try:
        return registry.alias_for_internal(raw_ref)
    except ValueError:
        pass
    try:
        registry.resolve(raw_ref, expected_kind=ReferenceObjectKind.NODE)
        return raw_ref
    except ValueError:
        return registry.register_existing(
            raw_ref,
            object_kind=ReferenceObjectKind.NODE,
            label="Node",
        )
