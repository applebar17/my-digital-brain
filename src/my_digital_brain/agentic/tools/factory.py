from __future__ import annotations

from collections.abc import Callable
from typing import Any

from my_digital_brain.agentic.state import AgenticStateConfig
from my_digital_brain.agentic.tools.bindings import (
    AgenticToolBindings,
    AgenticToolExecutionContext,
)
from my_digital_brain.agentic.tools.registry import (
    AgenticToolRegistry,
    default_agentic_tool_registry,
)
from my_digital_brain.ai.models import ToolResult
from my_digital_brain.ai.tools import ToolBox, build_tool_index


def build_agentic_toolbox(
    state_config: AgenticStateConfig,
    registry: AgenticToolRegistry | None = None,
) -> ToolBox:
    resolved_registry = registry or default_agentic_tool_registry()
    definitions = resolved_registry.definitions_for_state(state_config)
    tools = [definition.spec for definition in definitions]
    return ToolBox(
        name=f"agentic:{state_config.state_id}",
        tools=tools,
        tools_by_name=build_tool_index(tools),
    )


def build_agentic_tool_mapping(
    state_config: AgenticStateConfig,
    execution_context: AgenticToolExecutionContext,
    registry: AgenticToolRegistry | None = None,
) -> dict[str, Callable[..., ToolResult]]:
    resolved_registry = registry or default_agentic_tool_registry()
    definitions = resolved_registry.definitions_for_state(state_config)
    bindings = AgenticToolBindings(execution_context)
    mapping: dict[str, Callable[..., ToolResult]] = {}
    for definition in definitions:
        mapping[definition.name] = _named_handler(
            definition.name,
            bindings.handler_for(definition.handler_key),
        )
    return mapping


def _named_handler(name: str, handler: Callable[..., ToolResult]) -> Callable[..., ToolResult]:
    def wrapped(**kwargs: Any) -> ToolResult:
        return handler(**kwargs)

    wrapped.__name__ = name
    return wrapped
