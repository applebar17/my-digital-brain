from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from my_digital_brain.core.enums import LifecycleState
from my_digital_brain.graph.base import GraphServiceBase
from my_digital_brain.graph.constants import (
    AFFECTIVE_FIELD_NAMES,
    CHANGE_TARGET_KINDS,
    RELATIONSHIP_CONTEXT_CURRENT_FIELDS,
)
from my_digital_brain.graph.exceptions import GraphNotFoundError, GraphValidationError
from my_digital_brain.graph.models import (
    AffectiveContextResult,
    GraphRelationshipModel,
    LifecycleTransitionRequest,
    MemoryLogDetailResult,
    NodeSearchResult,
    RelationshipContextDetailResult,
    RelationshipResult,
)
from my_digital_brain.graph.utils import dump_change_value
from my_digital_brain.graph.write_service import GraphWriteService


class GraphMemoryService(GraphServiceBase):
    def __init__(self, repository: Any, writer: GraphWriteService) -> None:
        super().__init__(repository)
        self.writer = writer

    def get_affective_context(self, node_id: str, *, limit: int = 50) -> AffectiveContextResult:
        target = self.writer.get_node(node_id)
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
        context = self.writer.get_node(context_id)
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
        self.writer.upsert_relationship(
            "HAS_RELATIONSHIP_STATE",
            context_id,
            state.properties["id"],
            {},
        )

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
                self.writer.patch_node(context_id, changed_values)
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
        context = self.writer.get_node(context_id)
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
        context = self.writer.get_node(context_id)
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
            self.writer.upsert_relationship(
                "HAS_CHANGE_RECORD",
                target_id,
                change.properties["id"],
                {},
            )
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

    def get_memory_logs_for_target(
        self,
        target_id: str,
        *,
        limit: int = 50,
    ) -> list[NodeSearchResult]:
        records = self.repository.find_memory_logs_for_target(
            target_id,
            limit=self._bounded_limit(limit),
        )
        return [NodeSearchResult.model_validate(record) for record in records]

    def get_memory_log_detail(
        self,
        log_id: str,
        *,
        limit: int = 50,
    ) -> MemoryLogDetailResult:
        record = self.repository.get_memory_log_detail(
            log_id,
            limit=self._bounded_limit(limit),
        )
        if record is None:
            raise GraphNotFoundError(f"MemoryLog not found: {log_id}")

        memory_log = NodeSearchResult.model_validate(record["memory_log"])
        relationships = [
            RelationshipResult.model_validate(relationship)
            for relationship in record["relationships"]
        ]
        targets = [
            NodeSearchResult.model_validate(target)
            for target in record["targets"]
        ]
        target_by_id = {
            str(target.properties.get("id")): target
            for target in targets
            if target.properties.get("id")
        }
        hosts: list[NodeSearchResult] = []
        involved: list[NodeSearchResult] = []
        relationship_contexts: list[NodeSearchResult] = []
        media_assets: list[NodeSearchResult] = []

        for relationship in relationships:
            other_id = relationship.to_id if relationship.from_id == log_id else relationship.from_id
            target = target_by_id.get(other_id)
            if target is None:
                continue
            if relationship.type == "HAS_MEMORY_LOG":
                hosts.append(target)
            elif relationship.type == "INVOLVES":
                involved.append(target)
            elif relationship.type == "UPDATES_RELATIONSHIP":
                relationship_contexts.append(target)
            elif relationship.type == "HAS_MEDIA":
                media_assets.append(target)

        return MemoryLogDetailResult(
            memory_log=memory_log,
            hosts=_dedupe_nodes(hosts),
            involved=_dedupe_nodes(involved),
            relationship_contexts=_dedupe_nodes(relationship_contexts),
            media_assets=_dedupe_nodes(media_assets),
            relationships=relationships,
        )

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
        existing = self.writer.get_node(node_id)
        previous_state = existing.properties.get("lifecycle_state")
        patched = self.writer.patch_node(node_id, {"lifecycle_state": new_state})
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


def _dedupe_nodes(nodes: list[NodeSearchResult]) -> list[NodeSearchResult]:
    deduped: list[NodeSearchResult] = []
    seen: set[str] = set()
    for node in nodes:
        node_id = str(node.properties.get("id") or "")
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        deduped.append(node)
    return deduped
