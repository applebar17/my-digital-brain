from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from my_digital_brain.core.enums import LifecycleState, PrivacyLevel, TrustLevel
from my_digital_brain.graph.constants import NORMALIZED_NAME_LABELS
from my_digital_brain.graph.exceptions import GraphValidationError
from my_digital_brain.graph.models import NodeSearchResult, node_model_for_label
from my_digital_brain.graph.repository import GraphRepository
from my_digital_brain.graph.utils import normalize_text


class GraphServiceBase:
    def __init__(self, repository: GraphRepository) -> None:
        self.repository = repository

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
