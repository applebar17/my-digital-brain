from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from my_digital_brain.core.enums import LifecycleState, PrivacyLevel, TrustLevel
from my_digital_brain.graph.exceptions import (
    GraphConflictError,
    GraphNotFoundError,
    GraphValidationError,
)
from my_digital_brain.graph.models import (
    AffectiveContextResult,
    GraphRelationshipModel,
    LifecycleTransitionRequest,
    NeighborhoodResult,
    NodeSearchResult,
    RelationshipContextDetailResult,
    RelationshipResult,
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

NORMALIZED_NAME_LABELS = {"Person", "Place", "Organization", "Object", "Topic"}
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
ALIAS_LABELS = {"Person", "Organization", "Topic"}


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
