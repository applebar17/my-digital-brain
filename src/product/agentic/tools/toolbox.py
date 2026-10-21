"""Agent-specific composition of framework tool definitions and handlers."""

from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType

from pydantic import BaseModel

from product.agentic.tools.contracts import RegisteredTool
from product.ai.ai_clients.protocols.protocol_tools import ToolDefinitionDTO


class ToolBox:
    """Expose one state's tool definitions and their matching executable map."""

    def __init__(self, name: str, tools: Sequence[RegisteredTool]) -> None:
        self.name = name
        tools_by_name: dict[str, RegisteredTool] = {}
        for tool in tools:
            tool_name = tool.definition.name
            if tool_name in tools_by_name:
                raise ValueError(f"ToolBox '{name}' contains duplicate tool name '{tool_name}'.")
            tools_by_name[tool_name] = tool
        self.tools_by_name: Mapping[str, RegisteredTool] = MappingProxyType(tools_by_name)

    @property
    def definitions(self) -> list[ToolDefinitionDTO]:
        """Return framework definitions for the client to compile for its provider."""
        return [tool.definition for tool in self.tools_by_name.values()]

    @property
    def tools_mapping(self) -> Mapping[str, Callable[..., BaseModel]]:
        """Return handlers validating provider arguments against their registered input DTO."""
        return {name: tool.invoke for name, tool in self.tools_by_name.items()}
