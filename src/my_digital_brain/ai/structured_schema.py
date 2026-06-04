from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from pydantic import BaseModel


def strict_response_format(schema: type[BaseModel]) -> dict[str, Any]:
    """Build an OpenAI-compatible strict JSON schema response format."""

    strict_schema = strict_json_schema(schema.model_json_schema())
    return {
        "type": "json_schema",
        "json_schema": {
            "name": _schema_name(schema),
            "schema": strict_schema,
            "strict": True,
        },
    }


def strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize Pydantic JSON schema for provider strict structured outputs.

    OpenAI strict structured outputs require every object schema to explicitly
    set `additionalProperties: false`. Free-form dict fields are therefore
    represented as closed objects in the provider schema; backend Pydantic
    models still own final validation after the model response is returned.
    """

    normalized = deepcopy(schema)
    _normalize_node(normalized)
    return normalized


def _normalize_node(node: Any) -> None:
    if isinstance(node, dict):
        if _is_object_node(node):
            properties = node.get("properties")
            if not isinstance(properties, dict):
                properties = {}
                node["properties"] = properties
            node["additionalProperties"] = False
            node["required"] = sorted(str(key) for key in properties.keys())

        for keyword in ("allOf", "anyOf", "oneOf", "prefixItems"):
            children = node.get(keyword)
            if isinstance(children, list):
                for child in children:
                    _normalize_node(child)

        for keyword in ("items", "contains", "not", "if", "then", "else"):
            child = node.get(keyword)
            if isinstance(child, dict):
                _normalize_node(child)

        for keyword in ("properties", "$defs", "definitions", "dependentSchemas"):
            children = node.get(keyword)
            if isinstance(children, dict):
                for child in children.values():
                    _normalize_node(child)

    elif isinstance(node, list):
        for item in node:
            _normalize_node(item)


def _is_object_node(node: dict[str, Any]) -> bool:
    node_type = node.get("type")
    if node_type == "object":
        return True
    if isinstance(node_type, list) and "object" in node_type:
        return True
    return "properties" in node or "additionalProperties" in node


def _schema_name(schema: type[BaseModel]) -> str:
    raw = schema.__name__ or "StructuredOutput"
    normalized = re.sub(r"[^A-Za-z0-9_-]", "_", raw)
    return normalized[:64] or "StructuredOutput"
