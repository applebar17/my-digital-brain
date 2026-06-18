from __future__ import annotations

from collections.abc import Iterable, Mapping
import hashlib
import re
from typing import Any

from my_digital_brain.graph.models import NodeSearchResult
from my_digital_brain.ingestion.contracts.vector_scopes import VectorScopeName
from my_digital_brain.rag.models import EmbeddingDocument, HitRole

NODE_SUMMARY_LABELS = frozenset({"Person", "Place", "Event", "SocialCircle"})
CONTEXT_LABELS = frozenset(
    {"Claim", "Perception", "RelationshipContext", "RelationshipState", "ProfileMemory"}
)
MICRO_LOG_LABELS = frozenset({"MemoryLog"})
SUPPORTED_EMBEDDING_LABELS = NODE_SUMMARY_LABELS | CONTEXT_LABELS | MICRO_LOG_LABELS

MEANINGFUL_CONTEXT_KEYS = (
    "description",
    "emotional_summary",
    "original_user_words",
    "context_summary",
    "relationship_summary",
    "memory_summary",
    "recurring_context",
)


class EmbeddingTextBuilder:
    """Build deterministic, low-noise embedding documents from graph records."""

    def build_for_node(
        self,
        node: NodeSearchResult,
        *,
        related_nodes: Iterable[NodeSearchResult] | None = None,
        related_target_ids: Iterable[str] | None = None,
        relationship_ids: Iterable[str] | None = None,
        embedding_model: str | None = None,
    ) -> EmbeddingDocument | None:
        if node.label not in SUPPORTED_EMBEDDING_LABELS:
            return None
        route = _scope_route(node.label)
        if route is None:
            return None

        properties = node.properties
        primary_id = _text_value(properties.get("id"))
        if not primary_id:
            return None

        builder = getattr(self, f"_build_{_snake_case(node.label)}")
        document = builder(properties, list(related_nodes or []))
        if not document:
            return None

        embedding_scope = f"{_snake_case(node.label)}_summary"
        builder_version = f"{embedding_scope}.v1"
        related_ids = [
            *_related_ids_from_properties(properties),
            *[_node_id(related) for related in related_nodes or []],
            *(related_target_ids or []),
        ]
        related_ids = [value for value in related_ids if value and value != primary_id]

        return EmbeddingDocument(
            vector_id=_vector_id(embedding_scope, primary_id),
            collection=route.collection,
            embedding_scope=embedding_scope,
            primary_target_id=primary_id,
            primary_target_label=node.label,
            canonical_target_id=_canonical_target_id(node.label, properties),
            related_target_ids=related_ids,
            source_ids=_source_ids(properties, related_nodes or []),
            relationship_ids=list(relationship_ids or []),
            hit_role=route.hit_role,
            embedding_model=embedding_model,
            builder_version=builder_version,
            document_checksum=_checksum(document),
            lifecycle_state=_text_value(properties.get("lifecycle_state")) or "active",
            document=document,
        )

    def _build_claim(self, properties: Mapping[str, Any], _related: list[NodeSearchResult]) -> str | None:
        text = _text_value(properties.get("text"))
        if not text:
            return None
        return _document(
            _line("Claim", text),
            _line("Type", properties.get("claim_type")),
            _time_line(properties),
            _line("Evidence", properties.get("evidence_summary")),
        )

    def _build_event(self, properties: Mapping[str, Any], related: list[NodeSearchResult]) -> str | None:
        title = _first_text(properties, "title", "description")
        if not title:
            return None
        participants = _titles_for_labels(related, {"Person", "Animal", "Organization"})
        places = _titles_for_labels(related, {"Place"})
        return _document(
            _line("Event", title),
            _line("Description", properties.get("description")) if properties.get("description") != title else None,
            _time_line(properties),
            _line("Participants", participants),
            _line("Place", places),
            _affective_line(properties),
            _line("Original user wording", properties.get("original_user_words")),
        )

    def _build_perception(
        self,
        properties: Mapping[str, Any],
        related: list[NodeSearchResult],
    ) -> str | None:
        description = _first_text(properties, "description", "emotional_summary", "original_user_words")
        if not description:
            return None
        target_title = _titles_for_labels(related, set())
        subject = f" about {target_title}" if target_title else ""
        return _document(
            _line(f"Perception{subject}", description),
            _line("Type", properties.get("perception_type")),
            _line("Source kind", properties.get("source_kind")),
            _affective_line(properties),
            _line("Original user wording", properties.get("original_user_words")),
        )

    def _build_relationship_context(
        self,
        properties: Mapping[str, Any],
        related: list[NodeSearchResult],
    ) -> str | None:
        description = _first_text(properties, "description", "emotional_summary", "original_user_words")
        if not description:
            return None
        participants = _titles_for_labels(related, {"Person", "Animal", "Organization", "SocialCircle"})
        return _document(
            _line("Relationship", description),
            _line("Type", properties.get("relationship_type")),
            _line("Status", properties.get("status")),
            _line("Closeness", properties.get("closeness")),
            _line("Participants", participants),
            _time_line(properties),
            _affective_line(properties),
            _line("Original user wording", properties.get("original_user_words")),
        )

    def _build_relationship_state(
        self,
        properties: Mapping[str, Any],
        related: list[NodeSearchResult],
    ) -> str | None:
        if not _has_meaningful_context(properties) and not _time_line(properties):
            return None
        description = _first_text(properties, "description", "emotional_summary", "original_user_words")
        if not description:
            return None
        context = _titles_for_labels(related, {"RelationshipContext", "Person", "Animal", "Organization"})
        return _document(
            _line("Relationship state", description),
            _line("Status", properties.get("status")),
            _line("Closeness", properties.get("closeness")),
            _line("Context", context),
            _time_line(properties),
            _affective_line(properties),
            _line("Original user wording", properties.get("original_user_words")),
        )

    def _build_profile_memory(
        self,
        properties: Mapping[str, Any],
        _related: list[NodeSearchResult],
    ) -> str | None:
        value = _text_value(properties.get("value"))
        key = _text_value(properties.get("profile_key"))
        if not value and not key:
            return None
        headline = f"{key}: {value}" if key and value else key or value
        return _document(
            _line("Profile memory", headline),
            _line("Category", properties.get("category")),
            _line("Stability", properties.get("stability")),
            _line("Visibility", properties.get("visibility")),
        )

    def _build_memory_log(
        self,
        properties: Mapping[str, Any],
        related: list[NodeSearchResult],
    ) -> str | None:
        text = _first_text(properties, "log_text", "description")
        if not text:
            return None
        host_titles = _titles_for_ids_or_nodes(
            properties,
            related,
            id_keys=("primary_host_target_id", "host_target_ids"),
        )
        involved_titles = _titles_for_ids_or_nodes(
            properties,
            related,
            id_keys=("involved_target_ids", "relationship_context_target_ids"),
        )
        return _document(
            _line("Memory log", text),
            _line("Kind", properties.get("log_kind")),
            _time_line(properties),
            _line("Source kind", properties.get("source_kind")),
            _line("Primary host", host_titles),
            _line("Involved", involved_titles),
            _line("Original user wording", properties.get("original_user_words")),
        )

    def _build_person(self, properties: Mapping[str, Any], related: list[NodeSearchResult]) -> str | None:
        if not _has_meaningful_context(properties):
            return None
        name = _first_text(properties, "display_name", "name", "normalized_name")
        if not name:
            return None
        aliases = _list_text(properties.get("aliases"))
        context = _titles_for_labels(related, {"RelationshipContext", "SocialCircle", "Event"})
        return _document(
            _line("Person", name),
            _line("Aliases", aliases),
            _line("Description", properties.get("description")),
            _affective_line(properties),
            _line("Context", _first_text(properties, "context_summary", "relationship_summary") or context),
            _line("Original user wording", properties.get("original_user_words")),
        )

    def _build_place(self, properties: Mapping[str, Any], related: list[NodeSearchResult]) -> str | None:
        if not _has_meaningful_context(properties):
            return None
        name = _first_text(properties, "name", "display_name", "normalized_name")
        if not name:
            return None
        location = _join_text(
            properties.get("address"),
            properties.get("city"),
            properties.get("region"),
            properties.get("country"),
        )
        context = _titles_for_labels(related, {"Event", "Person", "Perception"})
        return _document(
            _line("Place", name),
            _line("Location", location),
            _line("Description", properties.get("description")),
            _affective_line(properties),
            _line("Context", _first_text(properties, "context_summary", "recurring_context") or context),
            _line("Original user wording", properties.get("original_user_words")),
        )

    def _build_social_circle(
        self,
        properties: Mapping[str, Any],
        related: list[NodeSearchResult],
    ) -> str | None:
        if not _has_meaningful_context(properties):
            return None
        name = _first_text(properties, "name", "display_name", "normalized_name")
        if not name:
            return None
        members = _titles_for_labels(related, {"Person", "Animal", "Organization"})
        return _document(
            _line("Social circle", name),
            _line("Type", properties.get("circle_type")),
            _line("Description", properties.get("description")),
            _affective_line(properties),
            _line("Members mentioned", members),
            _line("Original user wording", properties.get("original_user_words")),
        )


def _document(*lines: str | None) -> str | None:
    compacted = [_compact(line) for line in lines if line and _compact(line)]
    if not compacted:
        return None
    return "\n".join(compacted)


def _line(label: str, value: Any) -> str | None:
    text = _text_value(value)
    if not text:
        return None
    return f"{label}: {text}."


def _time_line(properties: Mapping[str, Any]) -> str | None:
    return _line(
        "Time",
        _first_text(
            properties,
            "original_time_text",
            "resolved_start",
            "valid_from",
            "source_time",
            "observed_at",
            "happened_at",
            "created_at",
        ),
    )


def _affective_line(properties: Mapping[str, Any]) -> str | None:
    summary = _text_value(properties.get("emotional_summary"))
    tags = _list_text(properties.get("emotion_tags"))
    if summary and tags:
        return f"Emotional context: {summary}. Tags: {tags}."
    return _line("Emotional context", summary or tags)


def _first_text(properties: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        text = _text_value(properties.get(key))
        if text:
            return text
    return None


def _text_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, bool | int | float):
        return str(value)
    if isinstance(value, list | tuple | set):
        return _list_text(value)
    return None


def _list_text(value: Any) -> str | None:
    if not isinstance(value, list | tuple | set):
        return _text_value(value)
    parts = [_text_value(item) for item in value]
    parts = [part for part in parts if part]
    return ", ".join(parts) if parts else None


def _join_text(*values: Any) -> str | None:
    parts = [_text_value(value) for value in values]
    parts = [part for part in parts if part]
    return ", ".join(parts) if parts else None


def _compact(value: str, *, max_chars: int = 600) -> str:
    compacted = re.sub(r"\s+", " ", value).strip()
    if len(compacted) <= max_chars:
        return compacted
    return f"{compacted[: max_chars - 1].rstrip()}..."


def _has_meaningful_context(properties: Mapping[str, Any]) -> bool:
    return any(_text_value(properties.get(key)) for key in MEANINGFUL_CONTEXT_KEYS)


def _titles_for_labels(nodes: Iterable[NodeSearchResult], labels: set[str]) -> str | None:
    titles: list[str] = []
    for node in nodes:
        if labels and node.label not in labels:
            continue
        title = _node_title(node)
        if title:
            titles.append(title)
    return _list_text(titles)


def _titles_for_ids_or_nodes(
    properties: Mapping[str, Any],
    nodes: Iterable[NodeSearchResult],
    *,
    id_keys: tuple[str, ...],
) -> str | None:
    ids: set[str] = set()
    for key in id_keys:
        ids.update(_ids_from_value(properties.get(key)))
    titles: list[str] = []
    for node in nodes:
        node_id = _node_id(node)
        if not ids or node_id in ids:
            title = _node_title(node)
            if title:
                titles.append(title)
    return _list_text(titles)


def _node_title(node: NodeSearchResult) -> str | None:
    return _first_text(
        node.properties,
        "display_name",
        "name",
        "title",
        "text",
        "profile_key",
        "value",
        "description",
    )


def _node_id(node: NodeSearchResult) -> str:
    return _text_value(node.properties.get("id")) or ""


def _source_ids(properties: Mapping[str, Any], related_nodes: Iterable[NodeSearchResult]) -> list[str]:
    values = [
        *_ids_from_value(properties.get("source_ids")),
        *_ids_from_value(properties.get("source_id")),
    ]
    for node in related_nodes:
        if node.label == "Source":
            values.extend(_ids_from_value(node.properties.get("id")))
        values.extend(_ids_from_value(node.properties.get("source_ids")))
    return _dedupe(values)


def _related_ids_from_properties(properties: Mapping[str, Any]) -> list[str]:
    keys = (
        "target_id",
        "target_ids",
        "related_target_ids",
        "participant_ids",
        "person_ids",
        "place_ids",
        "event_ids",
        "organization_ids",
        "relationship_context_ids",
        "perception_ids",
        "claim_ids",
        "primary_host_target_id",
        "host_target_ids",
        "involved_target_ids",
        "relationship_context_target_ids",
        "media_refs",
    )
    values: list[str] = []
    for key in keys:
        values.extend(_ids_from_value(properties.get(key)))
    return _dedupe(values)


def _ids_from_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list | tuple | set):
        ids: list[str] = []
        for item in value:
            if isinstance(item, str) and item:
                ids.append(item)
        return ids
    return []


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _snake_case(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def _checksum(document: str) -> str:
    return "sha256:" + hashlib.sha256(document.encode("utf-8")).hexdigest()


def _vector_id(embedding_scope: str, primary_target_id: str) -> str:
    route = _scope_route_from_embedding_scope(embedding_scope)
    collection = route.collection if route is not None else "unknown_scope"
    return f"{collection}:{embedding_scope}:{primary_target_id}"


class _ScopeRoute:
    def __init__(self, *, collection: str, hit_role: HitRole) -> None:
        self.collection = collection
        self.hit_role = hit_role


def _scope_route(label: str) -> _ScopeRoute | None:
    if label in NODE_SUMMARY_LABELS:
        return _ScopeRoute(
            collection=VectorScopeName.MEMORY_NODE_SUMMARIES.value,
            hit_role="domain_node",
        )
    if label in CONTEXT_LABELS:
        return _ScopeRoute(
            collection=VectorScopeName.MEMORY_CONTEXTS.value,
            hit_role="context",
        )
    if label in MICRO_LOG_LABELS:
        return _ScopeRoute(
            collection=VectorScopeName.MEMORY_MICRO_LOGS.value,
            hit_role="memory_log",
        )
    return None


def _scope_route_from_embedding_scope(embedding_scope: str) -> _ScopeRoute | None:
    label = "".join(part.title() for part in embedding_scope.removesuffix("_summary").split("_"))
    return _scope_route(label)


def _canonical_target_id(label: str, properties: Mapping[str, Any]) -> str | None:
    if label == "MemoryLog":
        return _text_value(properties.get("primary_host_target_id"))
    return None
