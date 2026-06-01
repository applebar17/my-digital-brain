from __future__ import annotations

from typing import Any

from my_digital_brain.core.ids import IdAliasMapper
from my_digital_brain.graph.models import NodeSearchResult
from my_digital_brain.ingestion.contracts import (
    IngestionContextPackage,
    Mention,
    MentionScan,
    SourceRecordRef,
)
from my_digital_brain.ingestion.enums import MentionKind

MENTION_KIND_TO_LABEL = {
    MentionKind.PERSON: "Person",
    MentionKind.PLACE: "Place",
    MentionKind.EVENT: "Event",
    MentionKind.ORGANIZATION: "Organization",
    MentionKind.OBJECT: "Object",
    MentionKind.ANIMAL: "Animal",
    MentionKind.SOCIAL_CIRCLE: "SocialCircle",
    MentionKind.TOPIC: "Topic",
    MentionKind.CLAIM: "Claim",
}

CONTEXT_DISPLAY_FIELDS = (
    "description",
    "display_name",
    "name",
    "title",
    "text",
    "normalized_name",
    "aliases",
    "city",
    "country",
    "status",
    "closeness",
    "relationship_type",
    "emotional_summary",
    "emotional_valence",
    "emotion_tags",
    "original_user_words",
    "source_ids",
    "resolved_start",
    "valid_from",
    "source_time",
)


class GraphIngestionContextRetriever:
    """Retrieve low-noise graph context for ingestion planning."""

    def __init__(
        self,
        graph_service: Any,
        *,
        per_mention_limit: int = 3,
        alias_mapper: IdAliasMapper | None = None,
    ) -> None:
        self.graph_service = graph_service
        self.per_mention_limit = per_mention_limit
        self.alias_mapper = alias_mapper or IdAliasMapper()

    def retrieve(
        self,
        source: SourceRecordRef,
        mention_scan: MentionScan,
    ) -> IngestionContextPackage:
        entities: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        notes: list[str] = []

        for mention in mention_scan.mentions:
            label = _label_for_mention(mention)
            if label is None:
                continue
            matches = self.graph_service.search_nodes(
                label=label,
                query=mention.possible_normalized_value or mention.text,
                limit=self.per_mention_limit,
            )
            if len(matches) > 1:
                notes.append(
                    f"Mention '{mention.text}' matched {len(matches)} existing {label} nodes."
                )
            for node in matches:
                node_id = node.properties["id"]
                if node_id in seen_ids:
                    continue
                seen_ids.add(node_id)
                entities.append(self._node_summary(node, mention))

        return IngestionContextPackage(
            source_id=source.source_id,
            aliases=self.alias_mapper.export_context_map(),
            entities=entities,
            notes=notes,
        )

    def _node_summary(
        self,
        node: NodeSearchResult,
        mention: Mention,
    ) -> dict[str, Any]:
        properties = node.properties
        alias = self._alias_for_node(node)
        summary: dict[str, Any] = {
            "alias": alias,
            "label": node.label,
            "matched_mention": mention.text,
        }
        title = _display_title(node)
        if title:
            summary["title"] = title
        for field in CONTEXT_DISPLAY_FIELDS:
            value = properties.get(field)
            if value not in (None, "", []):
                summary[field] = value
        return summary

    def _alias_for_node(self, node: NodeSearchResult) -> str:
        if node.label == "Source":
            prefix = "SOURCE"
        elif node.label == "Claim":
            prefix = "CLAIM"
        else:
            prefix = "NODE"
        return self.alias_mapper.alias_for(node.properties["id"], prefix)


def _label_for_mention(mention: Mention) -> str | None:
    return MENTION_KIND_TO_LABEL.get(MentionKind(mention.kind))


def _display_title(node: NodeSearchResult) -> str | None:
    for field in ("display_name", "name", "title", "text", "description"):
        value = node.properties.get(field)
        if isinstance(value, str) and value.strip():
            return value
    return None
