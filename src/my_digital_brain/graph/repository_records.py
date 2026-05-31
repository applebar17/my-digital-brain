from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from my_digital_brain.graph.exceptions import GraphConflictError
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
    return {
        "type": record["type"],
        "from_id": record["from_id"],
        "to_id": record["to_id"],
        "properties": from_neo4j_properties(record["properties"]),
    }


def raise_conflict_if_constraint_error(exc: Exception) -> None:
    class_name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    if "constraint" in class_name or "constraint" in message or "already exists" in message:
        raise GraphConflictError(str(exc)) from exc
