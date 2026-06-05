from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from my_digital_brain.ai.client import GenAIClient, GenAISettings
from my_digital_brain.ai.structured_schema import strict_response_format
from my_digital_brain.ai.tools import (
    build_chat_toolbox,
    build_tool_mapping,
)
from my_digital_brain.ingestion.contracts import MentionScanDraft
from my_digital_brain.ingestion.contracts import drafts as draft_contracts


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


def test_strict_response_format_closes_draft_objects_for_mention_scan() -> None:
    response_format = strict_response_format(MentionScanDraft)
    schema = response_format["json_schema"]["schema"]
    mention_schema = schema["$defs"]["MentionDraft"]

    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert schema["additionalProperties"] is False
    assert mention_schema["additionalProperties"] is False
    assert "source_id" not in schema["properties"]
    assert "mention_scan_id" not in schema["properties"]
    assert "metadata" not in schema["properties"]
    assert "mention_id" not in mention_schema["properties"]
    assert "metadata" not in mention_schema["properties"]
    _assert_all_objects_are_closed(schema)
    _assert_refs_have_no_siblings(schema)
    _assert_schema_has_no_defaults(schema)


def test_structured_call_sends_strict_json_schema_response_format() -> None:
    completion = CapturingChatCompletion()
    client = object.__new__(GenAIClient)
    client.client = SimpleNamespace(
        chat=SimpleNamespace(completions=completion),
    )

    parsed = client._call_structured_once(
        MentionScanDraft,
        messages=[{"role": "user", "content": "scan"}],
        model="test-model",
        temperature=None,
        max_tokens=None,
    )

    assert parsed.mentions == []
    response_format = completion.params["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "MentionScanDraft"
    assert "source_id" not in response_format["json_schema"]["schema"]["properties"]


def test_structured_call_rejects_empty_provider_content() -> None:
    completion = CapturingChatCompletion(content="")
    client = object.__new__(GenAIClient)
    client.client = SimpleNamespace(
        chat=SimpleNamespace(completions=completion),
    )

    with pytest.raises(ValueError, match="empty content"):
        client._call_structured_once(
            MentionScanDraft,
            messages=[{"role": "user", "content": "scan"}],
            model="test-model",
            temperature=None,
            max_tokens=None,
        )


def test_ingestion_draft_response_schemas_do_not_expose_backend_fields() -> None:
    output_schemas = [
        draft_contracts.MentionScanDraft,
        draft_contracts.SemanticIngestionPlanDraft,
        draft_contracts.CandidateEntityDraftBatch,
        draft_contracts.CandidateRelationshipDraftBatch,
        draft_contracts.CandidateClaimDraftBatch,
        draft_contracts.CandidatePerceptionDraftBatch,
        draft_contracts.CandidateRelationshipContextDraftBatch,
        draft_contracts.CandidateMetadataPatchDraftBatch,
    ]
    forbidden_fields = {
        "source_id",
        "source_refs",
        "evidence_refs",
        "metadata",
        "mention_id",
        "mention_scan_id",
        "extraction_plan_id",
        "task_id",
        "candidate_id",
        "candidate_relationship_id",
        "candidate_claim_id",
        "candidate_perception_id",
        "candidate_relationship_context_id",
        "patch_id",
        "typed_properties",
        "properties",
    }

    for schema_model in output_schemas:
        schema = strict_response_format(schema_model)["json_schema"]["schema"]
        _assert_no_forbidden_properties(schema, forbidden_fields)
        _assert_all_objects_are_closed(schema)
        _assert_refs_have_no_siblings(schema)


class CapturingChatCompletion:
    def __init__(self, content: str | None = None) -> None:
        self.params = {}
        self.content = content

    def create(self, **params):
        self.params = params
        content = self.content
        if content is None:
            content = json.dumps(
                {
                    "mentions": [],
                }
            )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        content=content,
                    )
                )
            ]
        )


def _assert_all_objects_are_closed(schema: object) -> None:
    if isinstance(schema, dict):
        if (
            schema.get("type") == "object"
            or "properties" in schema
            or "additionalProperties" in schema
        ):
            assert schema.get("additionalProperties") is False
        for value in schema.values():
            _assert_all_objects_are_closed(value)
    elif isinstance(schema, list):
        for item in schema:
            _assert_all_objects_are_closed(item)


def _assert_refs_have_no_siblings(schema: object) -> None:
    if isinstance(schema, dict):
        if "$ref" in schema:
            assert set(schema) == {"$ref"}
        for value in schema.values():
            _assert_refs_have_no_siblings(value)
    elif isinstance(schema, list):
        for item in schema:
            _assert_refs_have_no_siblings(item)


def _assert_no_forbidden_properties(
    schema: object,
    forbidden_fields: set[str],
) -> None:
    if isinstance(schema, dict):
        properties = schema.get("properties")
        if isinstance(properties, dict):
            assert forbidden_fields.isdisjoint(properties)
        for value in schema.values():
            _assert_no_forbidden_properties(value, forbidden_fields)
    elif isinstance(schema, list):
        for item in schema:
            _assert_no_forbidden_properties(item, forbidden_fields)


def _assert_schema_has_no_defaults(schema: object) -> None:
    if isinstance(schema, dict):
        assert "default" not in schema
        for value in schema.values():
            _assert_schema_has_no_defaults(value)
    elif isinstance(schema, list):
        for item in schema:
            _assert_schema_has_no_defaults(item)
