from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from my_digital_brain.graph.base import GraphServiceBase
from my_digital_brain.graph.constants import CONTRADICTION_STATUSES
from my_digital_brain.graph.exceptions import GraphNotFoundError, GraphValidationError
from my_digital_brain.graph.memory_service import GraphMemoryService
from my_digital_brain.graph.models import NodeSearchResult
from my_digital_brain.graph.utils import dump_change_value
from my_digital_brain.graph.write_service import GraphWriteService


class GraphContradictionService(GraphServiceBase):
    def __init__(
        self,
        repository: Any,
        writer: GraphWriteService,
        memory: GraphMemoryService,
    ) -> None:
        super().__init__(repository)
        self.writer = writer
        self.memory = memory

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
        contradiction = self.writer.upsert_node("ContradictionRecord", contradiction_properties)
        for target_id in target_ids:
            self.writer.upsert_relationship(
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
        existing = self.writer.get_node(contradiction_id)
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
        patched = self.writer.patch_node(contradiction_id, patch_properties)
        if previous_values:
            self.memory.create_change_record(
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
