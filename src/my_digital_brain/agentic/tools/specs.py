from __future__ import annotations

from typing import Any

from my_digital_brain.ai.models import ToolSpec


def tool_spec(
    name: str,
    description: str,
    properties: dict[str, dict[str, Any]] | None = None,
    required: list[str] | None = None,
) -> ToolSpec:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
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
        "description": description,
        "default": default,
        "minimum": minimum,
        "maximum": maximum,
    }


def boolean_property(description: str, *, default: bool = False) -> dict[str, Any]:
    return {"type": "boolean", "description": description, "default": default}


def object_property(description: str) -> dict[str, Any]:
    return {
        "type": "object",
        "description": description,
        "additionalProperties": True,
    }


def array_property(description: str) -> dict[str, Any]:
    return {
        "type": "array",
        "description": description,
        "items": {"type": "string"},
    }
