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

    def propose_memory_correction(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("propose_memory_correction", request))
        return ChatToolResult(
            status=ChatResponseStatus.NEEDS_USER_INPUT,
            primary_text="Correction requires confirmation.",
            metadata={"operation": "propose_memory_correction"},
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


def test_registry_validates_default_state_configs_and_memory_planning_state() -> None:
    configs = default_state_configs()
    registry = default_agentic_tool_registry()

    registry.validate_state_configs(configs)

    planning = configs[AgenticStateId.MEMORY_INGESTION_PLANNING]
    assert planning.prompt_id == "ingestion_planner"
    assert planning.allowed_tools == [
        "request_graph_context_expansion",
        "request_contradiction_review",
    ]
    assert "Plan extraction tasks" in PromptRegistry().load("ingestion_planner").template


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
        "propose_memory_correction",
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
        "propose_memory_correction",
    }

    result = mapping["start_memory_ingestion"](source_text="Yesterday I met Marco.")

    assert result.status == "ok"
    assert result.output == "Memory ingestion handoff requested."
    assert result.data["handoff_target"] == "memory_ingestion_precheck"
    assert result.data["handoff_arguments"]["source_text"] == "Yesterday I met Marco."
    assert execution_context.tool_events[0].data["handoff_target"] == (
        "memory_ingestion_precheck"
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


def test_correction_tools_produce_confirmation_aware_outputs_without_mutation() -> None:
    graph = FakeGraphService()
    config = default_state_configs()[AgenticStateId.CORRECTION_INTAKE]
    mapping = build_agentic_tool_mapping(config, _execution_context(graph_service=graph))

    resolved = mapping["resolve_correction_target"](
        correction_text="Marco was from university.",
    )
    proposal = mapping["build_correction_proposal"](
        correction_text="Marco was from university.",
        target_id="node-marco",
        target_label="Person",
        field_path="description",
        current_value={"description": "coworker"},
        proposed_value={"description": "university friend"},
        reason="The user corrected Marco's context.",
    )
    confirmation = mapping["request_user_confirmation"](
        question="Should I update Marco's description?",
        proposal=proposal.data["proposal"],
        target_refs=["node-marco"],
    )

    assert resolved.data["requires_clarification"] is False
    assert proposal.data["proposal"]["requires_confirmation"] is True
    assert confirmation.data["confirmation"]["required_user_action"] == "confirm_or_cancel"
    assert graph.mutations == []


def test_missing_dependency_returns_verbose_tool_error() -> None:
    config = default_state_configs()[AgenticStateId.MEMORY_QUERY]
    mapping = build_agentic_tool_mapping(config, _execution_context())

    result = mapping["get_context_package"](node_id="node-marco")

    assert result.status == "error"
    assert result.error.code == "missing_dependency"
    assert "graph_service" in result.error.message
    assert "Configure AgenticToolExecutionContext.graph_service" in result.error.hint


def test_memory_planning_context_expansion_uses_graph_service() -> None:
    graph = FakeGraphService()
    config = default_state_configs()[AgenticStateId.MEMORY_INGESTION_PLANNING]
    toolbox = build_agentic_toolbox(config)
    mapping = build_agentic_tool_mapping(config, _execution_context(graph_service=graph))

    result = mapping["request_graph_context_expansion"](query="Marco", limit=5)

    assert sorted(toolbox.tools_by_name) == [
        "request_contradiction_review",
        "request_graph_context_expansion",
    ]
    assert result.status == "ok"
    assert result.data["matches"][0]["properties"]["id"] == "node-marco"
    assert ("search_nodes", "Marco") in graph.calls


def test_memory_planning_contradiction_handoff_without_submit_tool() -> None:
    config = default_state_configs()[AgenticStateId.MEMORY_INGESTION_PLANNING]
    execution_context = _execution_context()
    mapping = build_agentic_tool_mapping(config, execution_context)

    contradiction = mapping["request_contradiction_review"](
        agent_doubt="The new place conflicts with existing event context.",
        proposed_write_ref="WRITE_000001",
        affected_entity_refs=["NODE_000001"],
        source_refs=["source-1"],
    )

    assert "submit_extraction_plan" not in mapping
    assert contradiction.status == "ok"
    assert contradiction.data["handoff_target"] == "contradiction_review"
    assert contradiction.data["handoff_arguments"]["agent_doubt"].startswith("The new place")
