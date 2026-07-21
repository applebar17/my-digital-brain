from __future__ import annotations

from my_digital_brain.ai.client import GenAISettings
from my_digital_brain.ai.structured_schema import strict_response_format
from my_digital_brain.ai.tools import (
    build_chat_toolbox,
    build_tool_mapping,
)
from my_digital_brain.ingestion.contracts import CandidateEntityDraftBatch
from my_digital_brain.ingestion.contracts import drafts as draft_contracts
from my_digital_brain.ingestion.contracts import memory_logs as memory_log_contracts
from my_digital_brain.ingestion.contracts import refined_drafts as refined_contracts


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


def test_strict_response_format_closes_candidate_draft_objects() -> None:
    response_format = strict_response_format(CandidateEntityDraftBatch)
    schema = response_format["json_schema"]["schema"]
    entity_schema = schema["$defs"]["CandidateEntityDraft"]

    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert schema["additionalProperties"] is False
    assert entity_schema["additionalProperties"] is False
    assert "source_id" not in schema["properties"]
    assert "metadata" not in schema["properties"]
    assert "candidate_id" not in entity_schema["properties"]
    assert "metadata" not in entity_schema["properties"]
    _assert_all_objects_are_closed(schema)
    _assert_refs_have_no_siblings(schema)
    _assert_schema_has_no_defaults(schema)


def test_ingestion_draft_response_schemas_do_not_expose_backend_fields() -> None:
    output_schemas = [
        refined_contracts.IngestionReasoningCheckpointDraft,
        refined_contracts.EntityIngestionPlanDraft,
        refined_contracts.RelationshipIngestionPlanDraft,
        refined_contracts.MissingEntityRequiredDraft,
        memory_log_contracts.MemoryLogDraftBatch,
        memory_log_contracts.NodeUpdatePlanDraft,
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
