from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from my_digital_brain.core.enums import LifecycleState, PrivacyLevel, TrustLevel
from my_digital_brain.core.ids import IdAliasMapper
from my_digital_brain.graph.exceptions import (
    GraphConflictError,
    GraphNotFoundError,
    GraphValidationError,
)
from my_digital_brain.graph.models import (
    AffectiveContextResult,
    EntityDetailResult,
    GraphAnalyticsItem,
    GraphAnalyticsSummary,
    GraphContextPackage,
    GraphRelationshipModel,
    GraphViewNode,
    GraphViewRelationship,
    GraphViewResult,
    LifecycleTransitionRequest,
    MapViewResult,
    NeighborhoodResult,
    NodeSearchResult,
    RelationshipContextDetailResult,
    RelationshipResult,
    TimelineItem,
    TimelineResult,
    node_model_for_label,
)
from my_digital_brain.graph.registry import (
    primary_core_label,
    validate_node_label,
    validate_relationship_direction,
    validate_relationship_type,
)
from my_digital_brain.graph.repository import GraphRepository

if TYPE_CHECKING:
    from my_digital_brain.storage.graph import GraphClient

NORMALIZED_NAME_LABELS = {
    "Person",
    "Place",
    "Organization",
    "Object",
    "Animal",
    "SocialCircle",
    "Topic",
}
IMMUTABLE_PATCH_FIELDS = {"id", "created_at"}
AFFECTIVE_FIELD_NAMES = {
    "emotional_summary",
    "emotional_valence",
    "emotional_intensity",
    "emotion_tags",
    "original_user_words",
}
RELATIONSHIP_CONTEXT_CURRENT_FIELDS = {
    "description",
    "status",
    "closeness",
    "emotional_summary",
    "emotional_valence",
    "emotional_intensity",
    "emotion_tags",
    "original_user_words",
    "valid_from",
    "valid_to",
    "resolved_start",
    "resolved_end",
    "time_precision",
    "time_basis",
    "timezone",
    "original_time_text",
}
NODE_LIKE_TARGET_KINDS = {
    "node",
    "relationship_context",
    "relationship_state",
    "claim",
    "perception",
    "contradiction_record",
    "merge_record",
}
CHANGE_TARGET_KINDS = NODE_LIKE_TARGET_KINDS | {"relationship"}
CONTRADICTION_STATUSES = {"detected", "needs_clarification", "resolved", "ignored"}
MERGE_STATUSES = {"proposed", "applied", "rejected", "archived", "reverted"}
SAFE_MERGE_LIST_FIELDS = {"aliases", "source_ids", "extraction_run_ids"}
ALIAS_LABELS = {"Person", "Organization", "Animal", "Topic"}
HISTORY_LABELS = {"RelationshipState", "ChangeRecord", "ContradictionRecord", "MergeRecord"}
HIDDEN_LIFECYCLE_STATES = {LifecycleState.ARCHIVED.value, LifecycleState.DELETED.value}
TIMELINE_TIME_FIELDS = (
    "resolved_start",
    "valid_from",
    "source_time",
    "observed_at",
    "received_at",
    "created_at",
)
DISPLAY_METADATA_FIELDS = (
    "address",
    "city",
    "region",
    "country",
    "place_precision",
    "species",
    "breed",
    "sex",
    "status",
    "known_since",
    "circle_type",
    "source_kind",
    "relationship_type",
    "closeness",
    "kind",
    "label",
    "label_text",
    "value",
    "provider",
    "external_id",
    "url",
    "category",
    "domain",
)
CONTEXT_FACT_FIELDS = (
    "description",
    "emotional_summary",
    "emotional_valence",
    "emotion_tags",
    "original_user_words",
    "status",
    "closeness",
    "known_since",
    "city",
    "country",
    "species",
    "breed",
    "circle_type",
)


class GraphService:
    def __init__(self, repository: GraphRepository) -> None:
        self.repository = repository

    @classmethod
    def from_client(cls, client: GraphClient) -> "GraphService":
        return cls(GraphRepository(client))

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

    def get_affective_context(self, node_id: str, *, limit: int = 50) -> AffectiveContextResult:
        target = self.get_node(node_id)
        bounded_limit = self._bounded_limit(limit)
        perceptions = [
            NodeSearchResult.model_validate(node)
            for node in self.repository.find_perceptions_for_target(node_id, limit=bounded_limit)
        ]
        relationship_contexts = [
            NodeSearchResult.model_validate(node)
            for node in self.repository.find_relationship_contexts_for_target(
                node_id,
                limit=bounded_limit,
            )
        ]
        affective_relationships = [
            RelationshipResult.model_validate(relationship)
            for relationship in self.repository.find_affective_relationships(
                node_id,
                limit=bounded_limit,
            )
        ]
        direct_fields = {
            key: value
            for key, value in target.properties.items()
            if key in AFFECTIVE_FIELD_NAMES and value not in (None, [], "")
        }
        return AffectiveContextResult(
            target=target,
            direct_affective_fields=direct_fields,
            perceptions=perceptions,
            relationship_contexts=relationship_contexts,
            affective_relationships=affective_relationships,
        )

    def create_relationship_state(
        self,
        context_id: str,
        properties: dict[str, Any],
        *,
        make_current: bool = True,
    ) -> NodeSearchResult:
        context = self.get_node(context_id)
        if context.label != "RelationshipContext":
            raise GraphValidationError(
                "Relationship states can only attach to RelationshipContext nodes"
            )

        state_properties = dict(properties)
        state_properties["is_current"] = make_current
        state_properties = self._normalize_node_properties("RelationshipState", state_properties)
        state_properties = self._add_write_timestamps(state_properties, is_create=True)
        state = NodeSearchResult.model_validate(
            self.repository.upsert_node("RelationshipState", state_properties)
        )
        self.upsert_relationship("HAS_RELATIONSHIP_STATE", context_id, state.properties["id"], {})

        if make_current:
            self.repository.clear_current_relationship_states(
                context_id,
                except_state_id=state.properties["id"],
                updated_at=datetime.now(UTC).isoformat(),
            )

        current_patch = {
            field: state.properties[field]
            for field in RELATIONSHIP_CONTEXT_CURRENT_FIELDS
            if field in state.properties
        }
        if make_current and current_patch:
            previous_values = {
                field: context.properties.get(field)
                for field in current_patch
                if context.properties.get(field) != current_patch[field]
            }
            changed_values = {
                field: value
                for field, value in current_patch.items()
                if context.properties.get(field) != value
            }
            if changed_values:
                self.patch_node(context_id, changed_values)
                self.create_change_record(
                    {
                        "target_kind": "relationship_context",
                        "target_id": context_id,
                        "target_label": "RelationshipContext",
                        "field_path": "current_relationship_state",
                        "previous_value_json": dump_change_value(previous_values),
                        "new_value_json": dump_change_value(changed_values),
                        "changed_by": "system",
                        "reason": "relationship_state_marked_current",
                        "source_ids": state.properties.get("source_ids", []),
                        "extraction_run_ids": state.properties.get("extraction_run_ids", []),
                    }
                )

        return state

    def get_relationship_states(
        self,
        context_id: str,
        *,
        limit: int = 50,
    ) -> list[NodeSearchResult]:
        context = self.get_node(context_id)
        if context.label != "RelationshipContext":
            raise GraphValidationError("Relationship state history requires a RelationshipContext")
        records = self.repository.get_relationship_states(
            context_id,
            limit=self._bounded_limit(limit),
        )
        return [NodeSearchResult.model_validate(record) for record in records]

    def get_relationship_context_detail(
        self,
        context_id: str,
        *,
        include_state_history: bool = False,
        limit: int = 50,
    ) -> RelationshipContextDetailResult:
        context = self.get_node(context_id)
        if context.label != "RelationshipContext":
            raise GraphValidationError("Relationship context detail requires a RelationshipContext")
        states = (
            self.get_relationship_states(context_id, limit=limit)
            if include_state_history
            else []
        )
        return RelationshipContextDetailResult(context=context, state_history=states)

    def create_change_record(self, properties: dict[str, Any]) -> NodeSearchResult:
        change_properties = dict(properties)
        target_kind = change_properties.get("target_kind")
        if target_kind not in CHANGE_TARGET_KINDS:
            raise GraphValidationError(f"Unsupported change target kind: {target_kind}")

        target_id = change_properties.get("target_id")
        if not isinstance(target_id, str) or not target_id:
            raise GraphValidationError("ChangeRecord requires target_id")

        if target_kind == "relationship":
            relationship = self.repository.get_relationship(target_id)
            if relationship is None:
                raise GraphNotFoundError(f"Graph relationship not found: {target_id}")
            change_properties.setdefault("target_relationship_type", relationship["type"])
        elif self.repository.get_node(target_id) is None:
            raise GraphNotFoundError(f"Graph node not found: {target_id}")

        change_properties.setdefault("changed_at", datetime.now(UTC).isoformat())
        change_properties = self._normalize_node_properties("ChangeRecord", change_properties)
        change_properties = self._add_write_timestamps(change_properties, is_create=True)
        change = NodeSearchResult.model_validate(
            self.repository.upsert_node("ChangeRecord", change_properties)
        )
        if target_kind != "relationship":
            self.upsert_relationship("HAS_CHANGE_RECORD", target_id, change.properties["id"], {})
        return change

    def get_change_records_for_target(
        self,
        target_id: str,
        *,
        target_kind: str | None = None,
        limit: int = 50,
    ) -> list[NodeSearchResult]:
        if target_kind is not None and target_kind not in CHANGE_TARGET_KINDS:
            raise GraphValidationError(f"Unsupported change target kind: {target_kind}")
        records = self.repository.find_change_records_for_target(
            target_id,
            target_kind=target_kind,
            limit=self._bounded_limit(limit),
        )
        return [NodeSearchResult.model_validate(record) for record in records]

    def transition_node_lifecycle(
        self,
        node_id: str,
        transition: LifecycleTransitionRequest,
    ) -> NodeSearchResult:
        new_state = self._validate_enum_value(
            transition.lifecycle_state,
            LifecycleState,
            "lifecycle_state",
        )
        existing = self.get_node(node_id)
        previous_state = existing.properties.get("lifecycle_state")
        patched = self.patch_node(node_id, {"lifecycle_state": new_state})
        self.create_change_record(
            {
                "target_kind": "node",
                "target_id": node_id,
                "target_label": existing.label,
                "field_path": "lifecycle_state",
                "previous_value_json": dump_change_value(previous_state),
                "new_value_json": dump_change_value(new_state),
                "changed_by": transition.changed_by,
                "reason": transition.reason,
                "source_ids": transition.source_ids,
                "extraction_run_ids": transition.extraction_run_ids,
                "metadata": transition.metadata,
            }
        )
        return patched

    def transition_relationship_lifecycle(
        self,
        relationship_id: str,
        transition: LifecycleTransitionRequest,
    ) -> RelationshipResult:
        new_state = self._validate_enum_value(
            transition.lifecycle_state,
            LifecycleState,
            "lifecycle_state",
        )
        relationship = self.repository.get_relationship(relationship_id)
        if relationship is None:
            raise GraphNotFoundError(f"Graph relationship not found: {relationship_id}")

        previous_state = relationship["properties"].get("lifecycle_state")
        patch_properties = self._add_write_timestamps(
            {"lifecycle_state": new_state},
            is_create=False,
        )
        merged_properties = dict(relationship["properties"])
        merged_properties.update(patch_properties)
        try:
            GraphRelationshipModel.model_validate(merged_properties)
        except ValidationError as exc:
            raise GraphValidationError(str(exc)) from exc

        patched = self.repository.patch_relationship(relationship_id, patch_properties)
        if patched is None:
            raise GraphNotFoundError(f"Graph relationship not found: {relationship_id}")
        self.create_change_record(
            {
                "target_kind": "relationship",
                "target_id": relationship_id,
                "target_relationship_type": relationship["type"],
                "field_path": "lifecycle_state",
                "previous_value_json": dump_change_value(previous_state),
                "new_value_json": dump_change_value(new_state),
                "changed_by": transition.changed_by,
                "reason": transition.reason,
                "source_ids": transition.source_ids,
                "extraction_run_ids": transition.extraction_run_ids,
                "metadata": transition.metadata,
            }
        )
        return RelationshipResult.model_validate(patched)

    def create_contradiction(
        self,
        properties: dict[str, Any],
        *,
        target_ids: list[str] | None = None,
    ) -> NodeSearchResult:
        target_ids = target_ids or []
        for target_id in target_ids:
            if self.repository.get_node(target_id) is None:
                raise GraphNotFoundError(f"Graph node not found: {target_id}")

        contradiction_properties = dict(properties)
        status = contradiction_properties.setdefault("status", "detected")
        if status not in CONTRADICTION_STATUSES:
            raise GraphValidationError(f"Unsupported contradiction status: {status}")
        contradiction_properties.setdefault("detected_at", datetime.now(UTC).isoformat())
        contradiction = self.upsert_node("ContradictionRecord", contradiction_properties)
        for target_id in target_ids:
            self.upsert_relationship(
                "HAS_CONTRADICTION_RECORD",
                target_id,
                contradiction.properties["id"],
                {},
            )
        return contradiction

    def query_contradictions(
        self,
        *,
        target_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        contradiction_type: str | None = None,
        limit: int = 50,
    ) -> list[NodeSearchResult]:
        if status is not None and status not in CONTRADICTION_STATUSES:
            raise GraphValidationError(f"Unsupported contradiction status: {status}")
        if target_id is not None and self.repository.get_node(target_id) is None:
            raise GraphNotFoundError(f"Graph node not found: {target_id}")
        records = self.repository.find_contradictions(
            target_id=target_id,
            status=status,
            severity=severity,
            contradiction_type=contradiction_type,
            limit=self._bounded_limit(limit),
        )
        return [NodeSearchResult.model_validate(record) for record in records]

    def update_contradiction(
        self,
        contradiction_id: str,
        properties: dict[str, Any],
    ) -> NodeSearchResult:
        existing = self.get_node(contradiction_id)
        if existing.label != "ContradictionRecord":
            raise GraphValidationError("Contradiction update requires a ContradictionRecord")
        if (
            properties.get("status") is not None
            and properties["status"] not in CONTRADICTION_STATUSES
        ):
            raise GraphValidationError(f"Unsupported contradiction status: {properties['status']}")

        patch_properties = dict(properties)
        if patch_properties.get("status") == "resolved":
            patch_properties.setdefault("resolved_at", datetime.now(UTC).isoformat())
        previous_values = {
            field: existing.properties.get(field)
            for field in patch_properties
            if existing.properties.get(field) != patch_properties[field]
        }
        patched = self.patch_node(contradiction_id, patch_properties)
        if previous_values:
            self.create_change_record(
                {
                    "target_kind": "contradiction_record",
                    "target_id": contradiction_id,
                    "target_label": "ContradictionRecord",
                    "field_path": "contradiction_record",
                    "previous_value_json": dump_change_value(previous_values),
                    "new_value_json": dump_change_value(patch_properties),
                    "changed_by": "system",
                    "reason": "contradiction_record_updated",
                }
            )
        return patched

    def create_merge_record(
        self,
        *,
        canonical_node_id: str,
        merged_node_ids: list[str],
        reason: str | None = None,
        performed_by: str = "system",
        source_ids: list[str] | None = None,
        extraction_run_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NodeSearchResult:
        canonical, merged_nodes = self._validate_merge_nodes(canonical_node_id, merged_node_ids)
        merge_properties = {
            "canonical_node_id": canonical.properties["id"],
            "merged_node_ids": [node.properties["id"] for node in merged_nodes],
            "reason": reason,
            "performed_by": performed_by,
            "status": "proposed",
            "source_ids": source_ids or [],
            "extraction_run_ids": extraction_run_ids or [],
            "metadata": metadata or {},
        }
        return self.upsert_node("MergeRecord", merge_properties)

    def query_merges(
        self,
        *,
        canonical_node_id: str | None = None,
        merged_node_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[NodeSearchResult]:
        if status is not None and status not in MERGE_STATUSES:
            raise GraphValidationError(f"Unsupported merge status: {status}")
        records = self.repository.find_merges(
            canonical_node_id=canonical_node_id,
            merged_node_id=merged_node_id,
            status=status,
            limit=self._bounded_limit(limit),
        )
        return [NodeSearchResult.model_validate(record) for record in records]

    def update_merge_record(self, merge_id: str, properties: dict[str, Any]) -> NodeSearchResult:
        existing = self.get_node(merge_id)
        if existing.label != "MergeRecord":
            raise GraphValidationError("Merge update requires a MergeRecord")
        status = properties.get("status")
        if status is not None:
            if status not in MERGE_STATUSES:
                raise GraphValidationError(f"Unsupported merge status: {status}")
            if status == "applied":
                raise GraphValidationError("Use the merge apply endpoint to apply a merge")
        return self.patch_node(merge_id, properties)

    def apply_merge(self, merge_id: str) -> NodeSearchResult:
        merge_record = self.get_node(merge_id)
        if merge_record.label != "MergeRecord":
            raise GraphValidationError("Merge apply requires a MergeRecord")
        status = merge_record.properties.get("status")
        if status == "applied":
            raise GraphConflictError(f"Merge record is already applied: {merge_id}")
        if status != "proposed":
            raise GraphConflictError(f"Only proposed merge records can be applied: {merge_id}")

        canonical_id = merge_record.properties["canonical_node_id"]
        merged_ids = list(merge_record.properties.get("merged_node_ids", []))
        canonical, merged_nodes = self._validate_merge_nodes(canonical_id, merged_ids)

        self.upsert_relationship("CANONICAL_NODE", merge_id, canonical_id, {})
        for merged_node in merged_nodes:
            merged_id = merged_node.properties["id"]
            self.upsert_relationship("MERGED_NODE", merge_id, merged_id, {})
            self.upsert_relationship("MERGED_INTO", merged_id, canonical_id, {})

        canonical_patch = self._safe_merge_patch(canonical, merged_nodes)
        if canonical_patch:
            previous_values = {
                field: canonical.properties.get(field)
                for field in canonical_patch
                if canonical.properties.get(field) != canonical_patch[field]
            }
            self.patch_node(canonical_id, canonical_patch)
            self.create_change_record(
                {
                    "target_kind": "node",
                    "target_id": canonical_id,
                    "target_label": canonical.label,
                    "field_path": "merge_safe_fields",
                    "previous_value_json": dump_change_value(previous_values),
                    "new_value_json": dump_change_value(canonical_patch),
                    "changed_by": merge_record.properties.get("performed_by") or "system",
                    "reason": merge_record.properties.get("reason"),
                    "source_ids": merge_record.properties.get("source_ids", []),
                    "extraction_run_ids": merge_record.properties.get("extraction_run_ids", []),
                }
            )

        for merged_node in merged_nodes:
            previous_values = {
                "lifecycle_state": merged_node.properties.get("lifecycle_state"),
                "merged_into_id": merged_node.properties.get("merged_into_id"),
            }
            patch = {
                "lifecycle_state": LifecycleState.ARCHIVED.value,
                "merged_into_id": canonical_id,
            }
            self.patch_node(merged_node.properties["id"], patch)
            self.create_change_record(
                {
                    "target_kind": "node",
                    "target_id": merged_node.properties["id"],
                    "target_label": merged_node.label,
                    "field_path": "merge_archive",
                    "previous_value_json": dump_change_value(previous_values),
                    "new_value_json": dump_change_value(patch),
                    "changed_by": merge_record.properties.get("performed_by") or "system",
                    "reason": merge_record.properties.get("reason"),
                    "source_ids": merge_record.properties.get("source_ids", []),
                    "extraction_run_ids": merge_record.properties.get("extraction_run_ids", []),
                }
            )

        return self.patch_node(
            merge_id,
            {"status": "applied", "merged_at": datetime.now(UTC).isoformat()},
        )

    def get_canonical_node(self, node_id: str) -> NodeSearchResult:
        current_id = node_id
        seen: set[str] = set()
        while True:
            if current_id in seen:
                raise GraphValidationError(f"Merge cycle detected while resolving {node_id}")
            seen.add(current_id)
            current = self.get_node(current_id)
            relationships = self.repository.get_node_relationships(
                current_id,
                relationship_type="MERGED_INTO",
                direction="out",
                limit=2,
            )
            if not relationships:
                return current
            if len(relationships) > 1:
                raise GraphValidationError(
                    f"Multiple canonical nodes found while resolving {node_id}"
                )
            current_id = relationships[0]["to_id"]

    def get_entity_detail(
        self,
        node_id: str,
        *,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 50,
    ) -> EntityDetailResult:
        target = self.get_node(node_id)
        bounded_limit = self._bounded_limit(limit)
        canonical = self.get_canonical_node(node_id)
        if canonical.properties["id"] == target.properties["id"]:
            canonical = None

        relationships = [
            relationship
            for relationship in self.get_node_relationships(node_id, limit=bounded_limit)
            if include_archived or not self._is_hidden_relationship(relationship)
        ]
        affective = self.get_affective_context(node_id, limit=bounded_limit)
        sources = self.get_source_evidence(node_id, limit=bounded_limit)
        changes = (
            self.get_change_records_for_target(node_id, limit=bounded_limit)
            if include_history
            else []
        )
        contradictions = self.query_contradictions(target_id=node_id, limit=bounded_limit)
        merges = self._dedupe_nodes(
            [
                *self.query_merges(canonical_node_id=node_id, limit=bounded_limit),
                *self.query_merges(merged_node_id=node_id, limit=bounded_limit),
            ]
        )

        return EntityDetailResult(
            target=target,
            canonical=canonical,
            relationships=relationships,
            perceptions=self._filter_visible_nodes(
                affective.perceptions,
                include_archived=include_archived,
                include_history=include_history,
            ),
            relationship_contexts=self._filter_visible_nodes(
                affective.relationship_contexts,
                include_archived=include_archived,
                include_history=include_history,
            ),
            sources=sources,
            changes=changes,
            contradictions=contradictions,
            merges=merges,
        )

    def get_memories_for_node(
        self,
        node_id: str,
        *,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 50,
    ) -> GraphViewResult:
        self.get_node(node_id)
        neighborhood = self.repository.get_related_records(
            node_id,
            depth=2,
            limit=self._bounded_limit(limit),
        )
        return self._to_graph_view_result(
            node_id,
            neighborhood,
            include_history=include_history,
            include_archived=include_archived,
        )

    def get_source_evidence(self, target_id: str, *, limit: int = 50) -> list[NodeSearchResult]:
        self.get_node(target_id)
        records = self.repository.find_sources_for_target(
            target_id,
            limit=self._bounded_limit(limit),
        )
        return [NodeSearchResult.model_validate(record) for record in records]

    def get_timeline_for_node(
        self,
        node_id: str,
        *,
        from_time: str | None = None,
        to_time: str | None = None,
        include_history: bool = False,
        limit: int = 100,
    ) -> TimelineResult:
        seed = self.get_node(node_id)
        from_time = self._validate_time_filter(from_time, "from_time")
        to_time = self._validate_time_filter(to_time, "to_time")
        if from_time and to_time and from_time > to_time:
            raise GraphValidationError("from_time cannot be later than to_time")

        neighborhood = self.repository.get_related_records(
            node_id,
            depth=2,
            limit=self._bounded_limit(limit),
        )
        items = [
            self._to_timeline_item(node)
            for node in neighborhood.nodes
            if self._node_can_be_timeline_item(node, include_history=include_history)
        ]
        items = [
            item
            for item in items
            if self._time_in_range(item.time_value, from_time=from_time, to_time=to_time)
        ]
        items.sort(key=self._timeline_sort_key)
        return TimelineResult(seed=seed, items=items[: self._bounded_limit(limit)])

    def get_neighborhood_view(
        self,
        *,
        seed_id: str,
        depth: int = 1,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 100,
    ) -> GraphViewResult:
        self.get_node(seed_id)
        if depth < 1 or depth > 3:
            raise GraphValidationError("Neighborhood depth must be between 1 and 3")
        neighborhood = self.repository.get_related_records(
            seed_id,
            depth=depth,
            limit=self._bounded_limit(limit),
        )
        return self._to_graph_view_result(
            seed_id,
            neighborhood,
            include_history=include_history,
            include_archived=include_archived,
        )

    def get_map_view(
        self,
        *,
        seed_id: str | None = None,
        city: str | None = None,
        country: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int = 100,
    ) -> MapViewResult:
        bounded_limit = self._bounded_limit(limit)
        from_time = self._validate_time_filter(from_time, "from_time")
        to_time = self._validate_time_filter(to_time, "to_time")
        if from_time and to_time and from_time > to_time:
            raise GraphValidationError("from_time cannot be later than to_time")

        if seed_id:
            self.get_node(seed_id)
            neighborhood = self.repository.get_related_records(
                seed_id,
                depth=2,
                limit=bounded_limit,
            )
        else:
            neighborhood = self.repository.find_map_records(
                city=city,
                country=country,
                limit=bounded_limit,
            )

        city_filter = normalize_text(city) if city else None
        country_filter = normalize_text(country) if country else None
        view = self._to_graph_view_result(
            seed_id or "",
            neighborhood,
            include_history=False,
            include_archived=False,
        )
        places = [
            node
            for node in view.nodes
            if node.label == "Place"
            and self._matches_location_filter(node, city=city_filter, country=country_filter)
        ]
        place_ids = {node.id for node in places}
        events = [
            node
            for node in view.nodes
            if node.label == "Event"
            and (
                not place_ids
                or any(
                    relationship.type == "HAPPENED_AT"
                    and relationship.from_id == node.id
                    and relationship.to_id in place_ids
                    for relationship in view.relationships
                )
            )
        ]
        map_node_ids = {node.id for node in places + events}
        relationships = [
            relationship
            for relationship in view.relationships
            if relationship.from_id in map_node_ids and relationship.to_id in map_node_ids
        ]
        timeline = [
            self._to_timeline_item(node)
            for node in neighborhood.nodes
            if node.properties.get("id") in map_node_ids
        ]
        timeline = [
            item
            for item in timeline
            if self._time_in_range(item.time_value, from_time=from_time, to_time=to_time)
        ]
        timeline.sort(key=self._timeline_sort_key)

        return MapViewResult(
            seed_id=seed_id,
            places=places,
            events=events,
            relationships=relationships,
            timeline=timeline[:bounded_limit],
        )

    def get_context_package(
        self,
        node_id: str,
        *,
        include_history: bool = True,
        timeline_limit: int = 20,
        relationship_limit: int = 50,
    ) -> GraphContextPackage:
        target = self.get_node(node_id)
        timeline_limit = self._bounded_limit(timeline_limit)
        relationship_limit = self._bounded_limit(relationship_limit)
        mapper = IdAliasMapper()

        target_summary = self._context_node_summary(target, mapper)
        relationships = [
            self._context_relationship_summary(relationship, mapper)
            for relationship in self.get_node_relationships(node_id, limit=relationship_limit)
            if not self._is_hidden_relationship(relationship)
        ]
        affective = self.get_affective_context(node_id, limit=relationship_limit)
        timeline = self.get_timeline_for_node(
            node_id,
            include_history=include_history,
            limit=timeline_limit,
        )
        evidence = self.get_source_evidence(node_id, limit=relationship_limit)
        contradictions = self.query_contradictions(
            target_id=node_id,
            status="detected",
            limit=relationship_limit,
        )
        canonical = self.get_canonical_node(node_id)

        notes: list[str] = []
        if canonical.properties["id"] != target.properties["id"]:
            canonical_alias = self._alias_for_node(canonical, mapper)
            notes.append(f"Node is merged into canonical alias {canonical_alias}.")
        for contradiction in contradictions:
            reason = contradiction.properties.get("reason") or "Unresolved contradiction."
            notes.append(f"Unresolved contradiction: {reason}")

        return GraphContextPackage(
            target=target_summary,
            current_facts=self._context_current_facts(target),
            relationships=relationships,
            relationship_contexts=[
                self._context_node_summary(node, mapper)
                for node in affective.relationship_contexts
            ],
            perceptions=[self._context_node_summary(node, mapper) for node in affective.perceptions],
            timeline=[
                self._context_timeline_item(item, mapper)
                for item in timeline.items[:timeline_limit]
            ],
            evidence=[self._context_node_summary(node, mapper) for node in evidence],
            notes=notes,
            alias_map=mapper.export_context_map(),
        )

    def get_analytics_summary(
        self,
        *,
        include_archived: bool = False,
        limit: int = 20,
    ) -> GraphAnalyticsSummary:
        bounded_limit = self._bounded_limit(limit)
        top_nodes = [
            GraphAnalyticsItem(
                key=item["node"]["properties"]["id"],
                count=item["count"],
                label=(
                    f"{item['node']['label']}: "
                    f"{self._display_title(NodeSearchResult.model_validate(item['node']))}"
                ),
            )
            for item in self.repository.top_connected_nodes(
                include_archived=include_archived,
                limit=bounded_limit,
            )
        ]
        top_tags = [
            GraphAnalyticsItem(key=item["tag"], count=item["count"])
            for item in self.repository.top_emotion_tags(
                include_archived=include_archived,
                limit=bounded_limit,
            )
        ]
        return GraphAnalyticsSummary(
            node_counts=self.repository.count_nodes_by_label(include_archived=include_archived),
            relationship_counts=self.repository.count_relationships_by_type(),
            top_connected_nodes=top_nodes,
            top_emotion_tags=top_tags,
            unresolved_contradictions=self.repository.count_unresolved_contradictions(),
        )

    def _to_graph_view_result(
        self,
        seed_id: str,
        neighborhood: NeighborhoodResult,
        *,
        include_history: bool,
        include_archived: bool,
    ) -> GraphViewResult:
        visible_nodes = self._filter_visible_nodes(
            neighborhood.nodes,
            include_archived=include_archived,
            include_history=include_history,
        )
        visible_ids = {node.properties["id"] for node in visible_nodes}
        visible_relationships = [
            relationship
            for relationship in neighborhood.relationships
            if relationship.from_id in visible_ids
            and relationship.to_id in visible_ids
            and (include_archived or not self._is_hidden_relationship(relationship))
        ]
        return GraphViewResult(
            seed_id=seed_id,
            nodes=[self._to_graph_view_node(node) for node in visible_nodes],
            relationships=[
                self._to_graph_view_relationship(relationship)
                for relationship in visible_relationships
            ],
        )

    def _filter_visible_nodes(
        self,
        nodes: list[NodeSearchResult],
        *,
        include_archived: bool,
        include_history: bool,
    ) -> list[NodeSearchResult]:
        return [
            node
            for node in nodes
            if (include_history or node.label not in HISTORY_LABELS)
            and (include_archived or not self._is_hidden_node(node))
        ]

    def _is_hidden_node(self, node: NodeSearchResult) -> bool:
        lifecycle_state = node.properties.get("lifecycle_state")
        return lifecycle_state in HIDDEN_LIFECYCLE_STATES or bool(
            node.properties.get("merged_into_id")
        )

    def _is_hidden_relationship(self, relationship: RelationshipResult) -> bool:
        return relationship.properties.get("lifecycle_state") in HIDDEN_LIFECYCLE_STATES

    def _to_graph_view_node(self, node: NodeSearchResult) -> GraphViewNode:
        properties = node.properties
        return GraphViewNode(
            id=properties["id"],
            label=node.label,
            title=self._display_title(node),
            description=self._display_description(node),
            lifecycle_state=properties.get("lifecycle_state"),
            privacy_level=properties.get("privacy_level"),
            trust_level=properties.get("trust_level"),
            emotional_summary=properties.get("emotional_summary"),
            temporal_summary=self._temporal_summary(properties),
            latitude=properties.get("latitude"),
            longitude=properties.get("longitude"),
            display_metadata=self._display_metadata(properties),
        )

    def _to_graph_view_relationship(
        self,
        relationship: RelationshipResult,
    ) -> GraphViewRelationship:
        properties = relationship.properties
        return GraphViewRelationship(
            id=properties["id"],
            type=relationship.type,
            from_id=relationship.from_id,
            to_id=relationship.to_id,
            description=properties.get("description"),
            lifecycle_state=properties.get("lifecycle_state"),
            emotional_summary=properties.get("emotional_summary"),
            temporal_summary=self._temporal_summary(properties),
        )

    def _to_timeline_item(self, node: NodeSearchResult) -> TimelineItem:
        properties = node.properties
        time_value, time_basis = self._timeline_time(properties)
        return TimelineItem(
            id=properties["id"],
            label=node.label,
            title=self._display_title(node),
            description=self._display_description(node),
            time_value=time_value,
            time_basis=properties.get("time_basis") or time_basis,
            time_precision=properties.get("time_precision"),
            source_ids=list(properties.get("source_ids", [])),
            emotional_summary=properties.get("emotional_summary"),
            original_user_words=properties.get("original_user_words"),
        )

    def _node_can_be_timeline_item(
        self,
        node: NodeSearchResult,
        *,
        include_history: bool,
    ) -> bool:
        if self._is_hidden_node(node):
            return False
        if not include_history and node.label in HISTORY_LABELS:
            return False
        return self._timeline_time(node.properties)[0] is not None

    def _timeline_sort_key(self, item: TimelineItem) -> tuple[int, str]:
        if item.time_value is None:
            return (1, "")
        return (0, item.time_value)

    def _timeline_time(self, properties: dict[str, Any]) -> tuple[str | None, str | None]:
        for field in TIMELINE_TIME_FIELDS:
            value = self._stringify_time(properties.get(field))
            if value:
                return value, field
        return None, None

    def _temporal_summary(self, properties: dict[str, Any]) -> str | None:
        time_value, basis = self._timeline_time(properties)
        if not time_value:
            return None
        precision = properties.get("time_precision")
        if precision:
            return f"{time_value} ({basis}, {precision})"
        if basis:
            return f"{time_value} ({basis})"
        return time_value

    def _display_title(self, node: NodeSearchResult) -> str:
        properties = node.properties
        for field in (
            "display_name",
            "name",
            "title",
            "text",
            "profile_key",
            "value",
            "external_id",
            "description",
        ):
            value = properties.get(field)
            if isinstance(value, str) and value.strip():
                return value
        return f"{node.label} {properties['id']}"

    def _display_description(self, node: NodeSearchResult) -> str | None:
        for field in ("description", "emotional_summary", "original_user_words", "text"):
            value = node.properties.get(field)
            if isinstance(value, str) and value.strip():
                return value
        return None

    def _display_metadata(self, properties: dict[str, Any]) -> dict[str, Any]:
        return {
            field: properties[field]
            for field in DISPLAY_METADATA_FIELDS
            if properties.get(field) not in (None, "", [])
        }

    def _matches_location_filter(
        self,
        node: GraphViewNode,
        *,
        city: str | None,
        country: str | None,
    ) -> bool:
        metadata_city = node.display_metadata.get("city")
        metadata_country = node.display_metadata.get("country")
        if city and normalize_text(str(metadata_city or "")) != city:
            return False
        if country and normalize_text(str(metadata_country or "")) != country:
            return False
        return True

    def _context_node_summary(
        self,
        node: NodeSearchResult,
        mapper: IdAliasMapper,
    ) -> dict[str, Any]:
        properties = node.properties
        summary = {
            "alias": self._alias_for_node(node, mapper),
            "label": node.label,
            "title": self._display_title(node),
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
        temporal_summary = self._temporal_summary(properties)
        if temporal_summary:
            summary["time"] = temporal_summary
        source_ids = properties.get("source_ids")
        if source_ids:
            summary["source_ids"] = source_ids
        return summary

    def _context_relationship_summary(
        self,
        relationship: RelationshipResult,
        mapper: IdAliasMapper,
    ) -> dict[str, Any]:
        properties = relationship.properties
        from_alias = self._alias_for_endpoint(relationship.from_id, mapper)
        to_alias = self._alias_for_endpoint(relationship.to_id, mapper)
        summary = {
            "alias": self._alias_for_id(properties["id"], "REL", mapper),
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
        temporal_summary = self._temporal_summary(properties)
        if temporal_summary:
            summary["time"] = temporal_summary
        return summary

    def _context_current_facts(self, node: NodeSearchResult) -> list[dict[str, Any]]:
        facts: list[dict[str, Any]] = []
        for field in CONTEXT_FACT_FIELDS:
            value = node.properties.get(field)
            if value not in (None, "", []):
                facts.append({"field": field, "value": value})
        temporal_summary = self._temporal_summary(node.properties)
        if temporal_summary:
            facts.append({"field": "time", "value": temporal_summary})
        return facts

    def _context_timeline_item(
        self,
        item: TimelineItem,
        mapper: IdAliasMapper,
    ) -> dict[str, Any]:
        prefix = "SOURCE" if item.label == "Source" else "CLAIM" if item.label == "Claim" else "NODE"
        summary = {
            "alias": self._alias_for_id(item.id, prefix, mapper),
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

    def _alias_for_node(self, node: NodeSearchResult, mapper: IdAliasMapper) -> str:
        if node.label == "Source":
            prefix = "SOURCE"
        elif node.label == "Claim":
            prefix = "CLAIM"
        else:
            prefix = "NODE"
        return self._alias_for_id(node.properties["id"], prefix, mapper)

    def _alias_for_endpoint(self, node_id: str, mapper: IdAliasMapper) -> str:
        node = self.repository.get_node(node_id)
        if node is None:
            return self._alias_for_id(node_id, "NODE", mapper)
        return self._alias_for_node(NodeSearchResult.model_validate(node), mapper)

    def _alias_for_id(self, internal_id: str, prefix: str, mapper: IdAliasMapper) -> str:
        try:
            return mapper.alias_for(internal_id, prefix)
        except ValueError as exc:
            raise GraphValidationError(
                "Graph context packages require UUID internal ids; "
                f"invalid id for {prefix}: {internal_id}"
            ) from exc

    def _validate_time_filter(self, value: str | None, field_name: str) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise GraphValidationError(f"{field_name} cannot be empty")
        try:
            datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError as exc:
            raise GraphValidationError(
                f"{field_name} must be an ISO date or datetime string"
            ) from exc
        return normalized

    def _time_in_range(
        self,
        value: str | None,
        *,
        from_time: str | None,
        to_time: str | None,
    ) -> bool:
        if value is None:
            return from_time is None and to_time is None
        if from_time and value < from_time:
            return False
        if to_time and value > to_time:
            return False
        return True

    def _stringify_time(self, value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str) and value.strip():
            return value
        return None

    def _dedupe_nodes(self, nodes: list[NodeSearchResult]) -> list[NodeSearchResult]:
        by_id: dict[str, NodeSearchResult] = {}
        for node in nodes:
            by_id[node.properties["id"]] = node
        return list(by_id.values())

    def _normalize_node_properties(self, label: str, properties: dict[str, Any]) -> dict[str, Any]:
        normalized_properties = dict(properties)
        if label in NORMALIZED_NAME_LABELS and not normalized_properties.get("normalized_name"):
            source_name = (
                normalized_properties.get("display_name")
                or normalized_properties.get("name")
                or normalized_properties.get("title")
            )
            if source_name:
                normalized_properties["normalized_name"] = normalize_text(source_name)
        if label == "ContactPoint" and not normalized_properties.get("normalized_value"):
            value = normalized_properties.get("value")
            if isinstance(value, str):
                normalized_properties["normalized_value"] = normalize_text(value)

        return self._validate_node_properties(label, normalized_properties)

    def _normalize_patch_properties(
        self,
        label: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_properties = dict(properties)
        if label in NORMALIZED_NAME_LABELS and "normalized_name" not in normalized_properties:
            source_name = (
                normalized_properties.get("display_name")
                or normalized_properties.get("name")
                or normalized_properties.get("title")
            )
            if isinstance(source_name, str):
                normalized_properties["normalized_name"] = normalize_text(source_name)
        if label == "ContactPoint" and "normalized_value" not in normalized_properties:
            value = normalized_properties.get("value")
            if isinstance(value, str):
                normalized_properties["normalized_value"] = normalize_text(value)
        return normalized_properties

    def _validate_node_properties(self, label: str, properties: dict[str, Any]) -> dict[str, Any]:
        model = node_model_for_label(label)
        try:
            node = model.model_validate(properties)
        except ValidationError as exc:
            raise GraphValidationError(str(exc)) from exc
        return node.model_dump(mode="python", by_alias=True, exclude_none=True)

    def _add_write_timestamps(
        self,
        properties: dict[str, Any],
        *,
        is_create: bool,
    ) -> dict[str, Any]:
        stamped = dict(properties)
        now = datetime.now(UTC).isoformat()
        if is_create:
            stamped.setdefault("created_at", now)
        stamped["updated_at"] = now
        return stamped

    def _validate_enum_value(
        self,
        value: str | None,
        enum_type: type[LifecycleState] | type[PrivacyLevel] | type[TrustLevel],
        field_name: str,
    ) -> str | None:
        if value is None:
            return None
        valid_values = {item.value for item in enum_type}
        if value not in valid_values:
            raise GraphValidationError(f"Unsupported {field_name}: {value}")
        return value

    def _bounded_limit(self, limit: int) -> int:
        if limit < 1:
            raise GraphValidationError("Limit must be greater than 0")
        return min(limit, 200)

    def _validate_merge_nodes(
        self,
        canonical_node_id: str,
        merged_node_ids: list[str],
    ) -> tuple[NodeSearchResult, list[NodeSearchResult]]:
        if not merged_node_ids:
            raise GraphValidationError("Merge requires at least one merged node")
        if canonical_node_id in merged_node_ids:
            raise GraphValidationError("Canonical node cannot be included in merged_node_ids")
        if len(set(merged_node_ids)) != len(merged_node_ids):
            raise GraphValidationError("Merge cannot contain duplicate merged_node_ids")

        canonical = self.get_node(canonical_node_id)
        merged_nodes = [self.get_node(node_id) for node_id in merged_node_ids]
        if any(node.label != canonical.label for node in merged_nodes):
            raise GraphValidationError("Merge nodes must share the same primary label")
        return canonical, merged_nodes

    def _safe_merge_patch(
        self,
        canonical: NodeSearchResult,
        merged_nodes: list[NodeSearchResult],
    ) -> dict[str, Any]:
        patch: dict[str, Any] = {}
        for field in SAFE_MERGE_LIST_FIELDS:
            if field == "aliases" and canonical.label not in ALIAS_LABELS:
                continue
            current_values = list(canonical.properties.get(field, []))
            merged_values: list[Any] = []
            for node in merged_nodes:
                values = node.properties.get(field, [])
                if isinstance(values, list):
                    merged_values.extend(values)
            merged = merge_unique_values(current_values, merged_values)
            if merged != current_values:
                patch[field] = merged
        return patch


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def dump_change_value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def merge_unique_values(existing: list[Any], additions: list[Any]) -> list[Any]:
    merged = list(existing)
    for value in additions:
        if value not in merged:
            merged.append(value)
    return merged
