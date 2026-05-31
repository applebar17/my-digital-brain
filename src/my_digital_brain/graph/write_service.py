from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from my_digital_brain.core.enums import LifecycleState, PrivacyLevel, TrustLevel
from my_digital_brain.graph.base import GraphServiceBase
from my_digital_brain.graph.constants import IMMUTABLE_PATCH_FIELDS
from my_digital_brain.graph.exceptions import GraphNotFoundError, GraphValidationError
from my_digital_brain.graph.models import (
    GraphRelationshipModel,
    NeighborhoodResult,
    NodeSearchResult,
    RelationshipResult,
)
from my_digital_brain.graph.registry import (
    primary_core_label,
    validate_node_label,
    validate_relationship_direction,
    validate_relationship_type,
)


class GraphWriteService(GraphServiceBase):
    def upsert_node(self, label: str, properties: dict[str, Any]) -> NodeSearchResult:
        label = validate_node_label(label)
        normalized_properties = self._normalize_node_properties(label, properties)
        normalized_properties = self._add_write_timestamps(normalized_properties, is_create=True)
        node = self.repository.upsert_node(label, normalized_properties)
        return NodeSearchResult.model_validate(node)

    def patch_node(self, node_id: str, properties: dict[str, Any]) -> NodeSearchResult:
        if IMMUTABLE_PATCH_FIELDS.intersection(properties):
            raise GraphValidationError("Node patches cannot change id or created_at")

        existing = self.repository.get_node(node_id)
        if existing is None:
            raise GraphNotFoundError(f"Graph node not found: {node_id}")

        label = primary_core_label(existing["labels"])
        patch_properties = self._normalize_patch_properties(label, properties)
        merged_properties = dict(existing["properties"])
        merged_properties.update(patch_properties)
        self._validate_node_properties(label, merged_properties)

        patch_properties = self._add_write_timestamps(patch_properties, is_create=False)
        patched = self.repository.patch_node(node_id, patch_properties)
        if patched is None:
            raise GraphNotFoundError(f"Graph node not found: {node_id}")
        return NodeSearchResult.model_validate(patched)

    def get_node(self, node_id: str) -> NodeSearchResult:
        node = self.repository.get_node(node_id)
        if node is None:
            raise GraphNotFoundError(f"Graph node not found: {node_id}")
        return NodeSearchResult.model_validate(node)

    def search_nodes(
        self,
        *,
        label: str | None = None,
        query: str | None = None,
        lifecycle_state: str | None = None,
        privacy_level: str | None = None,
        trust_level: str | None = None,
        limit: int = 25,
    ) -> list[NodeSearchResult]:
        if label:
            validate_node_label(label)
        lifecycle_state = self._validate_enum_value(
            lifecycle_state,
            LifecycleState,
            "lifecycle_state",
        )
        privacy_level = self._validate_enum_value(privacy_level, PrivacyLevel, "privacy_level")
        trust_level = self._validate_enum_value(trust_level, TrustLevel, "trust_level")
        limit = self._bounded_limit(limit)

        nodes = self.repository.search_nodes(
            label=label,
            query=query,
            lifecycle_state=lifecycle_state,
            privacy_level=privacy_level,
            trust_level=trust_level,
            limit=limit,
        )
        return [NodeSearchResult.model_validate(node) for node in nodes]

    def upsert_relationship(
        self,
        relationship_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any],
    ) -> RelationshipResult:
        relationship_type = validate_relationship_type(relationship_type)
        if self.repository.get_node(from_id) is None:
            raise GraphNotFoundError(f"Relationship source node not found: {from_id}")
        if self.repository.get_node(to_id) is None:
            raise GraphNotFoundError(f"Relationship target node not found: {to_id}")

        try:
            relationship_model = GraphRelationshipModel.model_validate(properties)
        except ValidationError as exc:
            raise GraphValidationError(str(exc)) from exc

        relationship_properties = relationship_model.model_dump(mode="python", exclude_none=True)
        relationship_properties = self._add_write_timestamps(
            relationship_properties,
            is_create=True,
        )
        relationship = self.repository.upsert_relationship(
            relationship_type,
            from_id,
            to_id,
            relationship_properties,
        )
        if relationship is None:
            raise GraphNotFoundError("Relationship endpoints were not found")
        return RelationshipResult.model_validate(relationship)

    def get_node_relationships(
        self,
        node_id: str,
        *,
        relationship_type: str | None = None,
        direction: str = "both",
        limit: int = 50,
    ) -> list[RelationshipResult]:
        if self.repository.get_node(node_id) is None:
            raise GraphNotFoundError(f"Graph node not found: {node_id}")
        if relationship_type:
            validate_relationship_type(relationship_type)
        validate_relationship_direction(direction)
        relationships = self.repository.get_node_relationships(
            node_id,
            relationship_type=relationship_type,
            direction=direction,
            limit=self._bounded_limit(limit),
        )
        return [RelationshipResult.model_validate(relationship) for relationship in relationships]

    def get_neighborhood(
        self,
        node_id: str,
        *,
        depth: int = 1,
        limit: int = 50,
    ) -> NeighborhoodResult:
        if self.repository.get_node(node_id) is None:
            raise GraphNotFoundError(f"Graph node not found: {node_id}")
        if depth < 1 or depth > 3:
            raise GraphValidationError("Neighborhood depth must be between 1 and 3")
        return self.repository.get_neighborhood(
            node_id,
            depth=depth,
            limit=self._bounded_limit(limit),
        )
