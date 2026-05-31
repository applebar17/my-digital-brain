from __future__ import annotations

from typing import Any

from my_digital_brain.core.ids import IdAliasMapper
from my_digital_brain.graph.constants import CONTEXT_FACT_FIELDS
from my_digital_brain.graph.exceptions import GraphValidationError
from my_digital_brain.graph.models import (
    AffectiveContextResult,
    GraphContextPackage,
    NodeSearchResult,
    RelationshipResult,
    TimelineResult,
)
from my_digital_brain.graph.projection import GraphProjection


class GraphContextPackageBuilder:
    def __init__(self, repository: Any, projection: GraphProjection) -> None:
        self.repository = repository
        self.projection = projection

    def build(
        self,
        *,
        target: NodeSearchResult,
        relationships: list[RelationshipResult],
        affective: AffectiveContextResult,
        timeline: TimelineResult,
        evidence: list[NodeSearchResult],
        contradictions: list[NodeSearchResult],
        canonical: NodeSearchResult,
        timeline_limit: int,
    ) -> GraphContextPackage:
        mapper = IdAliasMapper()
        target_summary = self.context_node_summary(target, mapper)

        notes: list[str] = []
        if canonical.properties["id"] != target.properties["id"]:
            canonical_alias = self.alias_for_node(canonical, mapper)
            notes.append(f"Node is merged into canonical alias {canonical_alias}.")
        for contradiction in contradictions:
            reason = contradiction.properties.get("reason") or "Unresolved contradiction."
            notes.append(f"Unresolved contradiction: {reason}")

        return GraphContextPackage(
            target=target_summary,
            current_facts=self.context_current_facts(target),
            relationships=[
                self.context_relationship_summary(relationship, mapper)
                for relationship in relationships
            ],
            relationship_contexts=[
                self.context_node_summary(node, mapper)
                for node in affective.relationship_contexts
            ],
            perceptions=[
                self.context_node_summary(node, mapper) for node in affective.perceptions
            ],
            timeline=[
                self.context_timeline_item(item, mapper)
                for item in timeline.items[:timeline_limit]
            ],
            evidence=[self.context_node_summary(node, mapper) for node in evidence],
            notes=notes,
            alias_map=mapper.export_context_map(),
        )

    def context_node_summary(
        self,
        node: NodeSearchResult,
        mapper: IdAliasMapper,
    ) -> dict[str, Any]:
        properties = node.properties
        summary = {
            "alias": self.alias_for_node(node, mapper),
            "label": node.label,
            "title": self.projection.display_title(node),
        }
        for field in (
            "description",
            "emotional_summary",
            "emotional_valence",
            "emotion_tags",
            "original_user_words",
            "status",
            "closeness",
            "relationship_type",
            "source_kind",
        ):
            value = properties.get(field)
            if value not in (None, "", []):
                summary[field] = value
        temporal_summary = self.projection.temporal_summary(properties)
        if temporal_summary:
            summary["time"] = temporal_summary
        source_ids = properties.get("source_ids")
        if source_ids:
            summary["source_ids"] = source_ids
        return summary

    def context_relationship_summary(
        self,
        relationship: RelationshipResult,
        mapper: IdAliasMapper,
    ) -> dict[str, Any]:
        properties = relationship.properties
        from_alias = self.alias_for_endpoint(relationship.from_id, mapper)
        to_alias = self.alias_for_endpoint(relationship.to_id, mapper)
        summary = {
            "alias": self.alias_for_id(properties["id"], "REL", mapper),
            "type": relationship.type,
            "from_alias": from_alias,
            "to_alias": to_alias,
        }
        for field in (
            "description",
            "emotional_summary",
            "emotional_valence",
            "emotion_tags",
            "original_user_words",
        ):
            value = properties.get(field)
            if value not in (None, "", []):
                summary[field] = value
        temporal_summary = self.projection.temporal_summary(properties)
        if temporal_summary:
            summary["time"] = temporal_summary
        return summary

    def context_current_facts(self, node: NodeSearchResult) -> list[dict[str, Any]]:
        facts: list[dict[str, Any]] = []
        for field in CONTEXT_FACT_FIELDS:
            value = node.properties.get(field)
            if value not in (None, "", []):
                facts.append({"field": field, "value": value})
        temporal_summary = self.projection.temporal_summary(node.properties)
        if temporal_summary:
            facts.append({"field": "time", "value": temporal_summary})
        return facts

    def context_timeline_item(
        self,
        item: Any,
        mapper: IdAliasMapper,
    ) -> dict[str, Any]:
        if item.label == "Source":
            prefix = "SOURCE"
        elif item.label == "Claim":
            prefix = "CLAIM"
        else:
            prefix = "NODE"
        summary = {
            "alias": self.alias_for_id(item.id, prefix, mapper),
            "label": item.label,
            "title": item.title,
            "time": item.time_value,
        }
        for field in ("description", "emotional_summary", "original_user_words"):
            value = getattr(item, field)
            if value not in (None, "", []):
                summary[field] = value
        if item.source_ids:
            summary["source_ids"] = item.source_ids
        return summary

    def alias_for_node(self, node: NodeSearchResult, mapper: IdAliasMapper) -> str:
        if node.label == "Source":
            prefix = "SOURCE"
        elif node.label == "Claim":
            prefix = "CLAIM"
        else:
            prefix = "NODE"
        return self.alias_for_id(node.properties["id"], prefix, mapper)

    def alias_for_endpoint(self, node_id: str, mapper: IdAliasMapper) -> str:
        node = self.repository.get_node(node_id)
        if node is None:
            return self.alias_for_id(node_id, "NODE", mapper)
        return self.alias_for_node(NodeSearchResult.model_validate(node), mapper)

    def alias_for_id(self, internal_id: str, prefix: str, mapper: IdAliasMapper) -> str:
        try:
            return mapper.alias_for(internal_id, prefix)
        except ValueError as exc:
            raise GraphValidationError(
                "Graph context packages require UUID internal ids; "
                f"invalid id for {prefix}: {internal_id}"
            ) from exc
