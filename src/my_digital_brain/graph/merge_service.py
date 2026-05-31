from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from my_digital_brain.core.enums import LifecycleState
from my_digital_brain.graph.base import GraphServiceBase
from my_digital_brain.graph.constants import ALIAS_LABELS, MERGE_STATUSES, SAFE_MERGE_LIST_FIELDS
from my_digital_brain.graph.exceptions import GraphConflictError, GraphValidationError
from my_digital_brain.graph.memory_service import GraphMemoryService
from my_digital_brain.graph.models import NodeSearchResult
from my_digital_brain.graph.utils import dump_change_value, merge_unique_values
from my_digital_brain.graph.write_service import GraphWriteService


class GraphMergeService(GraphServiceBase):
    def __init__(
        self,
        repository: Any,
        writer: GraphWriteService,
        memory: GraphMemoryService,
    ) -> None:
        super().__init__(repository)
        self.writer = writer
        self.memory = memory

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
        return self.writer.upsert_node("MergeRecord", merge_properties)

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
        existing = self.writer.get_node(merge_id)
        if existing.label != "MergeRecord":
            raise GraphValidationError("Merge update requires a MergeRecord")
        status = properties.get("status")
        if status is not None:
            if status not in MERGE_STATUSES:
                raise GraphValidationError(f"Unsupported merge status: {status}")
            if status == "applied":
                raise GraphValidationError("Use the merge apply endpoint to apply a merge")
        return self.writer.patch_node(merge_id, properties)

    def apply_merge(self, merge_id: str) -> NodeSearchResult:
        merge_record = self.writer.get_node(merge_id)
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

        self.writer.upsert_relationship("CANONICAL_NODE", merge_id, canonical_id, {})
        for merged_node in merged_nodes:
            merged_id = merged_node.properties["id"]
            self.writer.upsert_relationship("MERGED_NODE", merge_id, merged_id, {})
            self.writer.upsert_relationship("MERGED_INTO", merged_id, canonical_id, {})

        canonical_patch = self._safe_merge_patch(canonical, merged_nodes)
        if canonical_patch:
            previous_values = {
                field: canonical.properties.get(field)
                for field in canonical_patch
                if canonical.properties.get(field) != canonical_patch[field]
            }
            self.writer.patch_node(canonical_id, canonical_patch)
            self.memory.create_change_record(
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
            self.writer.patch_node(merged_node.properties["id"], patch)
            self.memory.create_change_record(
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

        return self.writer.patch_node(
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
            current = self.writer.get_node(current_id)
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

        canonical = self.writer.get_node(canonical_node_id)
        merged_nodes = [self.writer.get_node(node_id) for node_id in merged_node_ids]
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
