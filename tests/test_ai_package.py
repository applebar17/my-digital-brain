from __future__ import annotations

from my_digital_brain.ai.client import GenAISettings
from my_digital_brain.ai.tools import (
    build_chat_toolbox,
    build_tool_mapping,
)


def test_ai_client_settings_import_without_constructing_client() -> None:
    settings = GenAISettings(openai_api_key="test")

    assert settings.chat_model_default == "gpt-4o-mini"


def test_chat_toolbox_can_disable_search_tools() -> None:
    toolbox = build_chat_toolbox(enable_search=False)

    assert toolbox.name == "chat"
    assert toolbox.tools == []
    assert toolbox.tools_by_name == {}


def test_tool_mapping_exposes_searxng_handler() -> None:
    mapping = build_tool_mapping()

    assert sorted(mapping.keys()) == ["searxng_search"]
