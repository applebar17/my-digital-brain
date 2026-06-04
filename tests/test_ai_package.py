from __future__ import annotations

import json

import pytest

from my_digital_brain.ai.client import GenAIClient, GenAISettings
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


def test_genai_message_builder_wraps_structured_dict_payload_as_user_message() -> None:
    client = object.__new__(GenAIClient)

    messages = client._build_messages("Extract.", {"source": {"raw_text": "hello"}})

    assert messages[0] == {"role": "system", "content": "Extract."}
    assert messages[1]["role"] == "user"
    assert json.loads(messages[1]["content"]) == {"source": {"raw_text": "hello"}}


def test_genai_message_builder_preserves_valid_chat_message_sequence() -> None:
    client = object.__new__(GenAIClient)
    history = [
        {"role": "user", "content": "Remember dinner with Marco."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "start_memory_ingestion",
                        "arguments": "{}",
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": '{"status":"ok"}'},
    ]

    messages = client._build_messages("Route.", history)

    assert [message["role"] for message in messages] == [
        "system",
        "user",
        "assistant",
        "tool",
    ]
    assert messages[-1]["tool_call_id"] == "call-1"


def test_genai_message_builder_rejects_invalid_role_message() -> None:
    client = object.__new__(GenAIClient)

    with pytest.raises(ValueError, match="valid role"):
        client._build_messages("Route.", {"role": "invalid", "content": "bad"})


def test_genai_message_normalizer_repairs_roleless_payload_inside_messages() -> None:
    client = object.__new__(GenAIClient)

    messages = client._normalize_messages_for_chat(
        [
            {"role": "system", "content": "Extract."},
            {"source": {"raw_text": "hello"}},
        ]
    )

    assert [message["role"] for message in messages] == ["system", "user"]
    assert json.loads(messages[1]["content"]) == {"source": {"raw_text": "hello"}}
