"""Project-neutral toolbox definitions and tool-call mappings."""

from __future__ import annotations

import os
from collections.abc import Callable
from functools import partial
from typing import Any

from ..models import ToolResult
from .base import ToolBox, build_tool_index
from .searxng import SEARXNG_SEARCH_TOOL, searxng_search


def build_chat_toolbox(*, enable_search: bool | None = None) -> ToolBox:
    tools = []
    if _search_enabled(enable_search):
        tools.append(SEARXNG_SEARCH_TOOL)
    return ToolBox(name="chat", tools=tools, tools_by_name=build_tool_index(tools))


def build_research_toolbox(*, enable_search: bool | None = None) -> ToolBox:
    tools = []
    if _search_enabled(enable_search):
        tools.append(SEARXNG_SEARCH_TOOL)
    return ToolBox(name="research", tools=tools, tools_by_name=build_tool_index(tools))


def build_toolboxes(*, enable_search: bool | None = None) -> dict[str, ToolBox]:
    chat = build_chat_toolbox(enable_search=enable_search)
    research = build_research_toolbox(enable_search=enable_search)
    return {chat.name: chat, research.name: research}


def build_tool_mapping(**_unused: Any) -> dict[str, Callable[..., ToolResult]]:
    searxng_base_url = os.getenv("SEARXNG_BASE_URL")
    return {
        "searxng_search": partial(
            searxng_search,
            base_url=searxng_base_url,
        ),
    }


def build_tool_mapping_for(
    toolbox: ToolBox,
    **kwargs: Any,
) -> dict[str, Callable[..., ToolResult]]:
    mapping = build_tool_mapping(**kwargs)
    allowed = set(toolbox.tools_by_name.keys())
    return {name: handler for name, handler in mapping.items() if name in allowed}


def _search_enabled(value: bool | None) -> bool:
    if value is not None:
        return value
    return bool(os.getenv("SEARXNG_BASE_URL"))


TOOLBOXES = build_toolboxes()
CHAT_TOOLBOX = TOOLBOXES["chat"]
RESEARCH_TOOLBOX = TOOLBOXES["research"]
