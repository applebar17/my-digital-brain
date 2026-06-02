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
from my_digital_brain.ai.models import ToolError, ToolResult
from my_digital_brain.agentic.runtime_models import AgenticToolEvent
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
    execution_context.state_id = str(state_config.state_id)
    bindings = AgenticToolBindings(execution_context)
    mapping: dict[str, Callable[..., ToolResult]] = {}
    for definition in definitions:
        mapping[definition.name] = _named_handler(
            definition.name,
            bindings.handler_for(definition.handler_key),
            execution_context,
        )
    return mapping


def _named_handler(
    name: str,
    handler: Callable[..., ToolResult],
    execution_context: AgenticToolExecutionContext,
) -> Callable[..., ToolResult]:
    def wrapped(**kwargs: Any) -> ToolResult:
        try:
            result = handler(**kwargs)
        except Exception as exc:  # pragma: no cover - defensive boundary
            result = ToolResult(
                status="error",
                error=ToolError(
                    message=f"Tool '{name}' failed before backend handling: {exc}",
                    code="agentic_tool_exception",
                    type=exc.__class__.__name__,
                    hint="Check tool arguments and retry with the configured state toolbox.",
                    retryable=False,
                ),
            )
        execution_context.tool_events.append(_event_from_result(name, result))
        return result

    wrapped.__name__ = name
    return wrapped


def _event_from_result(name: str, result: ToolResult) -> AgenticToolEvent:
    return AgenticToolEvent(
        tool_name=name,
        status=result.status,
        output=result.output,
        data=_serializable_dict(result.data),
        error=(
            result.error.model_dump(mode="json", exclude_none=True)
            if result.error is not None
            else None
        ),
    )


def _serializable_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return {"value": value}
