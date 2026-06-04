from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from my_digital_brain.graph.exceptions import GraphConflictError, GraphValidationError
from my_digital_brain.graph.registry import primary_core_label
from my_digital_brain.graph.serialization import from_neo4j_properties


def node_from_record(record: Mapping[str, Any]) -> dict[str, Any]:
    labels = list(record["labels"])
    return {
        "label": primary_core_label(labels),
        "labels": labels,
        "properties": from_neo4j_properties(record["properties"]),
    }


def relationship_from_record(record: Mapping[str, Any]) -> dict[str, Any]:
    relationship_type = _first_present(
        record,
        "type",
        "_type",
        "relationship_type",
    )
    from_id = _first_present(record, "from_id", "start_id", "source_id")
    to_id = _first_present(record, "to_id", "end_id", "target_id")
    if relationship_type is None:
        raise GraphValidationError(
            "Relationship records must expose one of: type, _type, relationship_type."
        )
    if from_id is None or to_id is None:
        raise GraphValidationError(
            "Relationship records must expose endpoint ids as from_id/to_id, "
            "start_id/end_id, or source_id/target_id."
        )

    properties = from_neo4j_properties(record.get("properties") or {})
    properties.setdefault("id", f"{from_id}:{relationship_type}:{to_id}")
    return {
        "type": relationship_type,
        "from_id": from_id,
        "to_id": to_id,
        "properties": properties,
    }


def raise_conflict_if_constraint_error(exc: Exception) -> None:
    class_name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    if "constraint" in class_name or "constraint" in message or "already exists" in message:
        raise GraphConflictError(str(exc)) from exc


def _first_present(record: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return value
    return None
