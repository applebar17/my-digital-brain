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
from my_digital_brain.chat.enums import (
    ChatResponseStatus,
    PendingProcessKind,
    PendingProcessStatus,
)
from my_digital_brain.chat.facade import (
    CancelPendingProcessRequest,
    ChatToolRequest,
    ChatToolResult,
)
from my_digital_brain.chat.models import PendingProcessContext, PendingProcessRef
from my_digital_brain.chat.store import InMemoryChatSessionStore
from my_digital_brain.graph.models import (
    GraphViewNode,
    GraphViewResult,
    NodeSearchResult,
    RelationshipResult,
)
from my_digital_brain.prompts import PromptRegistry


class FakeFacade:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def start_memory_ingestion(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("start_memory_ingestion", request))
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="Memory accepted.",
            metadata={"operation": "start_memory_ingestion"},
        )

    def query_memory_context(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("query_memory_context", request))
        return ChatToolResult(
            status=ChatResponseStatus.OK,
            primary_text="Memory context found.",
            metadata={"operation": "query_memory_context"},
        )

    def update_memory_graph(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("update_memory_graph", request))
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="Graph update accepted.",
            metadata={"operation": "update_memory_graph"},
        )

    def get_conversation_status(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("get_conversation_status", request))
        return ChatToolResult(
            status=ChatResponseStatus.OK,
            primary_text="No pending process.",
            metadata={"operation": "get_conversation_status"},
        )

    def cancel_pending_process(self, request: CancelPendingProcessRequest) -> ChatToolResult:
        self.calls.append(("cancel_pending_process", request))
        return ChatToolResult(
            status=ChatResponseStatus.CANCELLED,
            primary_text="Cancelled.",
            metadata={"operation": "cancel_pending_process", "clear_pending_process": True},
        )

    def pause_pending_process(self, request: CancelPendingProcessRequest) -> ChatToolResult:
        self.calls.append(("pause_pending_process", request))
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="Paused.",
            metadata={"operation": "pause_pending_process", "clear_pending_process": True},
        )

    def resume_pending_process(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("resume_pending_process", request))
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="Resumed.",
            metadata={"operation": "resume_pending_process", "clear_pending_process": True},
        )


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


def _pending_context(
    process_id: str,
    *,
    question: str = "Which Marco?",
) -> PendingProcessContext:
    return PendingProcessContext(
        process_ref=PendingProcessRef(
            process_id=process_id,
            kind=PendingProcessKind.MEMORY_INGESTION,
            question=question,
        ),
        context={
            "summary": f"Pending memory clarification: {question}",
            "source_text": "Yesterday I met Marco in Milan.",
            "checkpoint_schema_version": "v1",
            "resume_step": "source_reprocess",
            "unresolved_targets": ["person: Marco"],
        },
    )


def test_registry_validates_default_state_configs_and_reasoning_planning_states() -> None:
    configs = default_state_configs()
    registry = default_agentic_tool_registry()

    registry.validate_state_configs(configs)

    reasoning = configs[AgenticStateId.REASONING_CHECKPOINT]
    generic_planning = configs[AgenticStateId.PLANNING_CHECKPOINT]
    assert reasoning.allowed_tools == [
        "get_context_package",
        "get_entity_detail",
        "get_neighborhood_view",
        "get_target_evidence",
        "request_user_clarification",
    ]
    assert "reasoning checkpoint for a network graph process" in PromptRegistry().load(
        "reasoning_checkpoint",
    ).template
    assert generic_planning.prompt_id == "planning_checkpoint"
    assert generic_planning.allowed_tools == [
        "get_context_package",
        "get_entity_detail",
        "get_neighborhood_view",
        "get_target_evidence",
        "request_user_clarification",
    ]
    assert "reusable planning checkpoint" in PromptRegistry().load(
        "planning_checkpoint",
    ).template


def test_state_toolboxes_expose_only_allowed_tools_and_no_forbidden_tools() -> None:
    registry = default_agentic_tool_registry()

    for state_config in default_state_configs().values():
        toolbox = build_agentic_toolbox(state_config, registry)
        names = set(toolbox.tools_by_name)

        assert names == set(state_config.allowed_tools)
        assert not names.intersection(state_config.forbidden_tools)

    entry_config = default_state_configs()[AgenticStateId.CONVERSATION_ENTRY]
    entry_toolbox = build_agentic_toolbox(entry_config, registry)
    assert set(entry_toolbox.tools_by_name) == {
        "start_memory_ingestion",
        "query_memory_context",
        "update_memory_graph",
    }


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

    with pytest.raises(ValueError, match="not registered for state conversation_entry"):
        registry.definitions_for_state(entry_config)


def test_top_level_tools_return_handoff_commands_without_facade_mutation() -> None:
    facade = FakeFacade()
    execution_context = _execution_context(backend_facade=facade)
    config = default_state_configs()[AgenticStateId.CONVERSATION_ENTRY]
    mapping = build_agentic_tool_mapping(config, execution_context)

    assert set(mapping) == {
        "start_memory_ingestion",
        "query_memory_context",
        "update_memory_graph",
    }

    result = mapping["start_memory_ingestion"](source_text="Yesterday I met Marco.")

    assert result.status == "accepted"
    assert result.output == "Memory ingestion handoff requested."
    assert result.data["handoff_target"] == "memory_ingestion_precheck"
    assert result.data["handoff_arguments"]["source_text"] == "Yesterday I met Marco."
    assert execution_context.tool_events[0].data["handoff_target"] == (
        "memory_ingestion_precheck"
    )
    assert facade.calls == []

    update = mapping["update_memory_graph"](
        source_text="Marco was from university, not work.",
        guidelines="Apply as a correction.",
        desired_work="correct_or_update_memory_graph",
        target_ids=["node-marco"],
        source_refs=[],
        metadata={},
    )

    assert update.status == "accepted"
    assert update.data["handoff_target"] == "graph_update"
    assert update.data["handoff_arguments"]["source_text"] == (
        "Marco was from university, not work."
    )
    assert facade.calls == []


def test_resume_pending_process_uses_current_text_without_user_reply_argument() -> None:
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel="web",
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    pending = _pending_context("process-1")
    store.save_pending_process_context(session.session_id, pending)
    facade = FakeFacade()
    config = default_state_configs()[AgenticStateId.PENDING_PROCESS_REVIEW]
    mapping = build_agentic_tool_mapping(
        config,
        _execution_context(
            backend_facade=facade,
            chat_store=store,
            session_id=session.session_id,
            current_text="Marco from university",
            pending_process_context=pending,
            pending_process_contexts=[pending],
        ),
    )

    schema = config.allowed_tools
    assert "resume_pending_process" in schema
    result = mapping["resume_pending_process"](pending_process_id="process-1")

    assert result.status == "ok"
    assert result.data["pending_process_id"] == "process-1"
    assert facade.calls[0][0] == "resume_pending_process"
    request = facade.calls[0][1]
    assert isinstance(request, ChatToolRequest)
    assert request.text == "Marco from university"
    assert request.pending_process_context.process_ref.process_id == "process-1"
    assert store.get_pending_process_context("process-1").process_ref.status == (
        PendingProcessStatus.COMPLETED
    )


def test_pause_pending_process_clears_active_and_preserves_resumable_context() -> None:
    store = InMemoryChatSessionStore()
    session = store.get_or_create_session(
        channel="web",
        external_conversation_id="conversation-1",
        owner_id="owner-1",
    )
    pending = _pending_context("process-1")
    store.save_pending_process_context(session.session_id, pending)
    config = default_state_configs()[AgenticStateId.PENDING_PROCESS_REVIEW]
    mapping = build_agentic_tool_mapping(
        config,
        _execution_context(
            chat_store=store,
            session_id=session.session_id,
            pending_process_context=pending,
            pending_process_contexts=[pending],
        ),
    )

    result = mapping["pause_pending_process"](
        pending_process_id="process-1",
        reason="I don't remember",
    )

    paused = store.get_pending_process_context("process-1")
    assert result.status == "ok"
    assert result.data["clear_pending_process"] is True
    assert paused.process_ref.status == PendingProcessStatus.PAUSED
    assert paused.context["resumable"] is True
    assert store.get_active_pending_process_context(session.session_id) is None


def test_pending_tool_requires_process_id_when_multiple_processes_exist() -> None:
    config = default_state_configs()[AgenticStateId.PENDING_PROCESS_REVIEW]
    mapping = build_agentic_tool_mapping(
        config,
        _execution_context(
            pending_process_contexts=[
                _pending_context("process-1"),
                _pending_context("process-2", question="Which Giovanni?"),
            ],
        ),
    )

    result = mapping["resume_pending_process"]()

    assert result.status == "error"
    assert result.error.code == "ambiguous_pending_process"
    assert result.error.details["available_process_ids"] == ["process-1", "process-2"]


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


def test_request_user_clarification_creates_pending_process_hint() -> None:
    config = default_state_configs()[AgenticStateId.MEMORY_QUERY]
    execution_context = _execution_context()
    mapping = build_agentic_tool_mapping(config, execution_context)

    result = mapping["request_user_clarification"](
        reason="Two people named Marco are plausible.",
        compact_summary="Need to identify which Marco the user means.",
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

    assert result.status == "needs_user_input"
    assert result.data["operation"] == "request_user_clarification"
    packet = result.data["clarification_packet"]
    pending = result.data["pending_process"]
    assert packet["process_id"] == pending["process_id"]
    assert packet["origin_state_id"] == AgenticStateId.MEMORY_QUERY.value
    assert packet["questions"][0]["options"][0]["label"] == "Marco from university"
    assert pending["kind"] == PendingProcessKind.MEMORY_QUERY.value
    assert pending["metadata"]["clarification_packet"]["packet_id"] == packet["packet_id"]
    assert execution_context.tool_events[0].status == "needs_user_input"


def test_request_user_clarification_is_not_exposed_to_conversation_entry() -> None:
    config = default_state_configs()[AgenticStateId.CONVERSATION_ENTRY]
    toolbox = build_agentic_toolbox(config)

    assert "request_user_clarification" not in toolbox.tools_by_name
