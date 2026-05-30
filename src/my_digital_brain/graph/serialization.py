from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


def dumps_metadata(metadata: Mapping[str, Any] | None) -> str:
    return json.dumps(metadata or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def loads_metadata(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        return {}
    return loaded


def normalize_property_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return normalize_property_value(value.model_dump(mode="json"))
    if isinstance(value, list):
        return [normalize_property_value(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_property_value(item) for item in value]
    return value


def to_neo4j_properties(
    properties: BaseModel | Mapping[str, Any],
    *,
    exclude_none: bool,
) -> dict[str, Any]:
    if isinstance(properties, BaseModel):
        raw = properties.model_dump(mode="json", by_alias=True, exclude_none=exclude_none)
    else:
        raw = dict(properties)
        if exclude_none:
            raw = {key: value for key, value in raw.items() if value is not None}

    encoded: dict[str, Any] = {}
    for key, value in raw.items():
        if key == "metadata":
            encoded["metadata_json"] = dumps_metadata(value)
        else:
            encoded[key] = normalize_property_value(value)
    return encoded


def from_neo4j_properties(properties: Mapping[str, Any]) -> dict[str, Any]:
    decoded = dict(properties)
    metadata_json = decoded.pop("metadata_json", None)
    decoded["metadata"] = loads_metadata(metadata_json)
    return decoded
