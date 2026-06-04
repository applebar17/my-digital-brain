from __future__ import annotations

from typing import Any

from my_digital_brain.ai.models import ToolSpec


def tool_spec(
    name: str,
    description: str,
    properties: dict[str, dict[str, Any]] | None = None,
    required: list[str] | None = None,
) -> ToolSpec:
    resolved_properties = {
        key: strict_schema_property(value)
        for key, value in (properties or {}).items()
    }
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": resolved_properties,
                "required": list(resolved_properties),
                "additionalProperties": False,
            },
            "strict": True,
        },
    }


def string_property(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def optional_string_property(description: str) -> dict[str, Any]:
    return {"type": ["string", "null"], "description": description}


def integer_property(description: str, *, default: int, minimum: int = 1, maximum: int = 200):
    return {
        "type": "integer",
        "description": f"{description} If unsure, use {default}.",
        "minimum": minimum,
        "maximum": maximum,
    }


def boolean_property(description: str, *, default: bool = False) -> dict[str, Any]:
    return {
        "type": "boolean",
        "description": f"{description} If unsure, use {str(default).lower()}.",
    }


def object_property(description: str) -> dict[str, Any]:
    return {
        "type": "object",
        "description": description,
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }


def array_property(description: str) -> dict[str, Any]:
    return {
        "type": "array",
        "description": description,
        "items": {"type": "string"},
    }


def strict_schema_property(schema: dict[str, Any]) -> dict[str, Any]:
    """Return an OpenAI strict-tool-compatible copy of a JSON schema property."""

    normalized = dict(schema)
    schema_type = normalized.get("type")
    is_object = schema_type == "object" or (
        isinstance(schema_type, list) and "object" in schema_type
    )
    if is_object:
        properties = normalized.get("properties")
        normalized["properties"] = {
            key: strict_schema_property(value)
            for key, value in (properties or {}).items()
        }
        normalized["required"] = list(normalized["properties"])
        normalized["additionalProperties"] = False
    normalized.pop("default", None)

    if normalized.get("type") == "array" and isinstance(normalized.get("items"), dict):
        normalized["items"] = strict_schema_property(normalized["items"])

    return normalized
