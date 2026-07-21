from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from my_digital_brain.agentic import (
    AgenticStateId,
    AgenticToolExecutionContext,
    build_agentic_tool_mapping,
    build_agentic_toolbox,
    default_agentic_tool_registry,
    default_state_configs,
)
from my_digital_brain.graph.models import (
    GraphViewNode,
    GraphViewResult,
    NodeSearchResult,
    RelationshipResult,
)
from my_digital_brain.prompts import PromptRegistry



class FakeContextPackage(BaseModel):
    target: dict[str, Any]
    alias_map: dict[str, str] = {}


class FakeGraphService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.mutations: list[str] = []

    def search_nodes(
        self,
        *,
        label: str | None = None,
        query: str | None = None,
        lifecycle_state: str | None = None,
        privacy_level: str | None = None,
        trust_level: str | None = None,
        limit: int = 25,
    ) -> list[NodeSearchResult]:
        self.calls.append(("search_nodes", query))
        return [
            NodeSearchResult(
                label="Person",
                labels=["Person"],
                properties={"id": "node-marco", "display_name": "Marco"},
            )
        ]

    def get_node(self, node_id: str) -> NodeSearchResult:
        self.calls.append(("get_node", node_id))
        return NodeSearchResult(
            label="Person",
            labels=["Person"],
            properties={"id": node_id, "display_name": "Marco"},
        )

    def get_context_package(
        self,
        node_id: str,
        *,
        include_history: bool = True,
        timeline_limit: int = 20,
        relationship_limit: int = 50,
    ) -> FakeContextPackage:
        self.calls.append(("get_context_package", node_id))
        return FakeContextPackage(
            target={"alias": "NODE_000001", "title": "Marco"},
            alias_map={"NODE_000001": node_id},
        )

    def get_entity_detail(
        self,
        node_id: str,
        *,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 50,
    ) -> dict[str, Any]:
        self.calls.append(("get_entity_detail", node_id))
        return {"target": {"id": node_id, "title": "Marco"}}

    def get_memories_for_node(
        self,
        node_id: str,
        *,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 50,
    ) -> dict[str, Any]:
        self.calls.append(("get_memories_for_node", node_id))
        return {"seed_id": node_id, "nodes": []}

    def get_timeline_for_node(
        self,
        node_id: str,
        *,
        from_time: str | None = None,
        to_time: str | None = None,
        include_history: bool = False,
        limit: int = 100,
    ) -> dict[str, Any]:
        self.calls.append(("get_timeline_for_node", node_id))
        return {"seed_id": node_id, "items": []}

    def get_neighborhood_view(
        self,
        *,
        seed_id: str,
        depth: int = 1,
        include_history: bool = False,
        include_archived: bool = False,
        limit: int = 100,
    ) -> GraphViewResult:
        self.calls.append(("get_neighborhood_view", seed_id))
        return GraphViewResult(
            seed_id=seed_id,
            nodes=[
                GraphViewNode(
                    id="contact-1",
                    label="ContactPoint",
                    title="email",
                    display_metadata={"value": "marco@example.com"},
                )
            ],
            relationships=[],
        )

    def get_map_view(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("get_map_view", kwargs))
        return {"places": [], "events": []}

    def get_source_evidence(self, target_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        self.calls.append(("get_source_evidence", target_id))
        return [{"id": "source-1", "title": "Chat"}]

    def get_change_records_for_target(
        self,
        target_id: str,
        *,
        target_kind: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self.calls.append(("get_change_records_for_target", target_id))
        return [{"id": "change-1"}]

    def get_relationship_states(self, context_id: str, *, limit: int = 50):
        self.calls.append(("get_relationship_states", context_id))
        return [{"id": "state-1"}]

    def upsert_node(self, label: str, properties: dict[str, Any]) -> NodeSearchResult:
        node_id = str(properties.get("id") or f"{label.lower()}-1")
        self.mutations.append(f"upsert_node:{label}:{node_id}")
        return NodeSearchResult(
            label=label,
            labels=[label],
            properties={**properties, "id": node_id},
        )

    def patch_node(self, node_id: str, properties: dict[str, Any]) -> NodeSearchResult:
        self.mutations.append(f"patch_node:{node_id}")
        return NodeSearchResult(
            label="Person",
            labels=["Person"],
            properties={"id": node_id, **properties},
        )

    def upsert_relationship(
        self,
        relationship_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any],
    ):
        self.mutations.append(f"upsert_relationship:{relationship_type}:{from_id}:{to_id}")
        return RelationshipResult(
            type=relationship_type,
            from_id=from_id,
            to_id=to_id,
            properties={"id": f"{from_id}:{relationship_type}:{to_id}", **properties},
        )

    def create_relationship_state(
        self,
        context_id: str,
        properties: dict[str, Any],
        *,
        make_current: bool = True,
    ) -> NodeSearchResult:
        self.mutations.append(f"create_relationship_state:{context_id}")
        return NodeSearchResult(
            label="RelationshipState",
            labels=["RelationshipState"],
            properties={"id": "state-1", **properties, "is_current": make_current},
        )


def _execution_context(**kwargs: Any) -> AgenticToolExecutionContext:
    defaults = {
        "session_id": "session-1",
        "conversation_id": "conversation-1",
        "owner_id": "owner-1",
        "channel": "web",
        "current_text": "Yesterday I met Marco.",
    }
    return AgenticToolExecutionContext(**{**defaults, **kwargs})


def test_registry_validates_default_state_configs_and_reasoning_planning_states() -> None:
    configs = default_state_configs()
    registry = default_agentic_tool_registry()

    registry.validate_state_configs(configs)

    reasoning = configs[AgenticStateId.REASONING_CHECKPOINT]
    generic_planning = configs[AgenticStateId.PLANNING_CHECKPOINT]
    memory_log_extraction = configs[AgenticStateId.MEMORY_LOG_EXTRACTION]
    assert reasoning.allowed_tools == [
        "get_context_package",
        "get_entity_detail",
        "get_neighborhood_view",
        "get_target_evidence",
        "ask_clarification",
    ]
    assert "structured reasoning notes" in PromptRegistry().load(
        "reasoning_checkpoint",
    ).template
    assert generic_planning.prompt_id == "planning_checkpoint"
    assert generic_planning.allowed_tools == [
        "get_context_package",
        "get_entity_detail",
        "get_neighborhood_view",
        "get_target_evidence",
        "ask_clarification",
    ]
    assert "ordered process actions" in PromptRegistry().load(
        "planning_checkpoint",
    ).template
    assert memory_log_extraction.allowed_tools == generic_planning.allowed_tools
    assert "memory-log ingestor" in PromptRegistry().load(
        "memory_log_extraction",
    ).template


def test_wave2_entry_tools_are_registered_and_active_on_entry() -> None:
    registry = default_agentic_tool_registry()
    entry_config = default_state_configs()[AgenticStateId.CONVERSATION_ENTRY]

    assert {"query_memory", "ingest_memory", "run_memory_creation"}.issubset(
        registry.definitions,
    )
    assert "start_memory_ingestion" not in registry.definitions
    assert "query_memory_context" not in registry.definitions
    assert entry_config.allowed_tools == ["query_memory", "ingest_memory"]

    ingest_params = registry.get("ingest_memory").spec["function"]["parameters"]
    assert ingest_params["properties"] == {}
    assert ingest_params["required"] == []
    assert "source_text" not in ingest_params["properties"]


def test_state_toolboxes_expose_only_allowed_tools_and_no_forbidden_tools() -> None:
    registry = default_agentic_tool_registry()

    for state_config in default_state_configs().values():
        toolbox = build_agentic_toolbox(state_config, registry)
        names = set(toolbox.tools_by_name)

        assert names == set(state_config.allowed_tools)
        assert not names.intersection(state_config.forbidden_tools)

    entry_config = default_state_configs()[AgenticStateId.CONVERSATION_ENTRY]
    entry_toolbox = build_agentic_toolbox(entry_config, registry)
    assert set(entry_toolbox.tools_by_name) == {"query_memory", "ingest_memory"}


def test_agentic_tool_schemas_are_strict_openai_compatible() -> None:
    registry = default_agentic_tool_registry()

    for state_config in default_state_configs().values():
        toolbox = build_agentic_toolbox(state_config, registry)
        for tool in toolbox.tools:
            function = tool["function"]
            assert function["strict"] is True
            _assert_objects_disallow_additional_properties(
                function["parameters"],
                path=function["name"],
            )


def _assert_objects_disallow_additional_properties(schema: dict[str, Any], *, path: str) -> None:
    schema_type = schema.get("type")
    if schema_type == "object" or (
        isinstance(schema_type, list) and "object" in schema_type
    ):
        assert schema.get("additionalProperties") is False, path
        properties = schema.get("properties", {})
        assert schema.get("required", []) == list(properties), path
        assert "default" not in schema, path
        for key, child in properties.items():
            _assert_objects_disallow_additional_properties(child, path=f"{path}.{key}")
    else:
        assert "default" not in schema, path
    if schema_type == "array" and isinstance(schema.get("items"), dict):
        _assert_objects_disallow_additional_properties(schema["items"], path=f"{path}[]")


def test_registry_rejects_pending_tools_on_conversation_entry() -> None:
    registry = default_agentic_tool_registry()
    entry_config = default_state_configs()[AgenticStateId.CONVERSATION_ENTRY].model_copy(
        update={"allowed_tools": ["cancel_pending_process"]},
        deep=True,
    )

    with pytest.raises(ValueError, match="not registered"):
        registry.definitions_for_state(entry_config)


def test_top_level_tools_require_agentic_runtime_without_legacy_facade() -> None:
    execution_context = _execution_context()
    config = default_state_configs()[AgenticStateId.CONVERSATION_ENTRY]
    mapping = build_agentic_tool_mapping(config, execution_context)

    assert set(mapping) == {"query_memory", "ingest_memory"}

    query = mapping["query_memory"](
        question="What do I remember about Marco?",
        seed_id=None,
        desired_view=None,
        metadata={},
    )
    ingest = mapping["ingest_memory"]()

    assert query.status == "error"
    assert query.error is not None
    assert query.error.code == "missing_dependency"
    assert "agentic_runtime" in query.error.message
    assert ingest.status == "error"
    assert ingest.error is not None
    assert ingest.error.code == "missing_dependency"
    assert "agentic_runtime" in ingest.error.message

def test_graph_read_tools_call_graph_service_and_serialize_results() -> None:
    graph = FakeGraphService()
    config = default_state_configs()[AgenticStateId.MEMORY_QUERY]
    mapping = build_agentic_tool_mapping(config, _execution_context(graph_service=graph))

    context = mapping["get_context_package"](node_id="node-marco")
    contacts = mapping["get_latest_contact_details"](node_id="node-marco")

    assert context.status == "ok"
    assert context.data["result"]["alias_map"] == {"NODE_000001": "node-marco"}
    assert contacts.data["result"]["contacts"][0]["display_metadata"]["value"] == (
        "marco@example.com"
    )
    assert ("get_context_package", "node-marco") in graph.calls
    assert ("get_neighborhood_view", "node-marco") in graph.calls


def test_graph_update_tools_execute_direct_writes_and_report_shared_outputs() -> None:
    graph = FakeGraphService()
    config = default_state_configs()[AgenticStateId.GRAPH_UPDATE]
    mapping = build_agentic_tool_mapping(config, _execution_context(graph_service=graph))

    resolved = mapping["resolve_graph_update_targets"](
        query="Marco was from university.",
        target_ids=[],
    )
    log = mapping["create_memory_log"](
        log_text="Marco was from university, not work.",
        host_target_ids=["node-marco"],
        primary_host_target_id=None,
        involved_target_ids=[],
        relationship_context_target_ids=[],
        media_refs=[],
        log_kind="correction",
        source_kind="chat",
        happened_at=None,
    )
    patch = mapping["patch_graph_node"](
        node_id="node-marco",
        properties_json='{"description":"university friend"}',
    )
    blocked = mapping["patch_graph_node"](
        node_id="node-marco",
        properties_json='{"lifecycle_state":"archived"}',
    )

    assert resolved.data["requires_clarification"] is False
    assert log.status == "ok"
    assert log.data["created_refs"]
    assert log.data["affected_graph_ids"] == ["memorylog-1", "node-marco"]
    assert patch.status == "ok"
    assert patch.data["updated_refs"] == ["node-marco"]
    assert blocked.status == "blocked"
    assert blocked.data["error_code"] == "destructive_lifecycle_not_allowed"
    assert any(item.startswith("upsert_node:MemoryLog") for item in graph.mutations)
    assert "patch_node:node-marco" in graph.mutations


def test_missing_dependency_returns_verbose_tool_error() -> None:
    config = default_state_configs()[AgenticStateId.MEMORY_QUERY]
    mapping = build_agentic_tool_mapping(config, _execution_context())

    result = mapping["get_context_package"](node_id="node-marco")

    assert result.status == "error"
    assert result.error.code == "missing_dependency"
    assert "graph_service" in result.error.message
    assert "Configure AgenticToolExecutionContext.graph_service" in result.error.hint


def test_ask_clarification_creates_frame_packet() -> None:
    config = default_state_configs()[AgenticStateId.GRAPH_UPDATE]
    execution_context = _execution_context(frame_id="frame-1")
    mapping = build_agentic_tool_mapping(config, execution_context)

    result = mapping["ask_clarification"](
        reason="Two people named Marco are plausible.",
        target_refs=["NODE_000001", "NODE_000002"],
        questions=[
            {
                "question": "Which Marco do you mean?",
                "options": [
                    {"label": "Marco from university", "recommended": True},
                    {"label": "Marco from work", "description": "Former coworker"},
                ],
                "free_text_allowed": True,
                "required": True,
                "selection_mode": "single",
            }
        ],
    )

    assert result.status == "pending"
    assert result.data["operation"] == "ask_clarification"
    assert result.data["frame_id"] == "frame-1"
    packet = result.data["clarification_packet"]
    assert "pending_process" not in result.data
    assert packet["frame_id"] == "frame-1"
    assert packet["origin_state_id"] == AgenticStateId.GRAPH_UPDATE.value
    assert packet["questions"][0]["options"][0]["label"] == "Marco from university"
    assert packet["history_delta"][0]["role"] == "assistant"
    assert "Which Marco do you mean?" in packet["history_delta"][0]["content"]
    assert result.data["history_delta"] == packet["history_delta"]
    assert execution_context.tool_events[0].status == "pending"


def test_ask_clarification_is_not_exposed_to_conversation_entry() -> None:
    config = default_state_configs()[AgenticStateId.CONVERSATION_ENTRY]
    toolbox = build_agentic_toolbox(config)

    assert "ask_clarification" not in toolbox.tools_by_name


def test_ask_clarification_is_not_exposed_to_memory_query() -> None:
    config = default_state_configs()[AgenticStateId.MEMORY_QUERY]
    toolbox = build_agentic_toolbox(config)

    assert "ask_clarification" not in toolbox.tools_by_name


def test_child_frame_tools_fail_visibly_without_runtime_or_plan_action() -> None:
    ingestion_config = default_state_configs()[AgenticStateId.MEMORY_INGESTION]
    ingestion_mapping = build_agentic_tool_mapping(
        ingestion_config,
        _execution_context(state_id=AgenticStateId.MEMORY_INGESTION.value),
    )
    creation = ingestion_mapping["run_memory_creation"](
        action_id="ACTION_001",
        metadata={},
    )
    update = ingestion_mapping["update_memory_graph"](
        source_text="Marco was from university.",
        guidelines=None,
        desired_work="update_node",
        target_ids=["node-marco"],
        source_refs=[],
        metadata={},
    )

    assert creation.status == "recoverable_error"
    assert creation.data["error_code"] == "memory_plan_action_not_found"
    assert update.status == "error"
    assert update.error is not None
    assert update.error.code == "missing_dependency"
    assert "agentic_runtime" in update.error.message
