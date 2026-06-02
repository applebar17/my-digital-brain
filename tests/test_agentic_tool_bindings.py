from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from my_digital_brain.agentic import (
    AgenticStateId,
    AgenticToolExecutionContext,
    build_agentic_tool_mapping,
    build_agentic_toolbox,
    default_agentic_tool_registry,
    default_state_configs,
)
from my_digital_brain.chat.enums import ChatResponseStatus
from my_digital_brain.chat.facade import (
    CancelPendingProcessRequest,
    ChatToolRequest,
    ChatToolResult,
)
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
            metadata={"operation": "cancel_pending_process"},
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
    return AgenticToolExecutionContext(
        session_id="session-1",
        conversation_id="conversation-1",
        owner_id="owner-1",
        channel="web",
        current_text="Yesterday I met Marco.",
        **kwargs,
    )


def test_registry_validates_default_state_configs_and_memory_planning_state() -> None:
    configs = default_state_configs()
    registry = default_agentic_tool_registry()

    registry.validate_state_configs(configs)

    planning = configs[AgenticStateId.MEMORY_INGESTION_PLANNING]
    assert planning.prompt_id == "ingestion_planner"
    assert planning.allowed_tools == ["request_graph_context_expansion"]
    assert "Plan extraction tasks" in PromptRegistry().load("ingestion_planner").template


def test_state_toolboxes_expose_only_allowed_tools_and_no_forbidden_tools() -> None:
    registry = default_agentic_tool_registry()

    for state_config in default_state_configs().values():
        toolbox = build_agentic_toolbox(state_config, registry)
        names = set(toolbox.tools_by_name)

        assert names == set(state_config.allowed_tools)
        assert not names.intersection(state_config.forbidden_tools)


def test_top_level_tools_call_backend_facade() -> None:
    facade = FakeFacade()
    config = default_state_configs()[AgenticStateId.CONVERSATION_ENTRY]
    mapping = build_agentic_tool_mapping(config, _execution_context(backend_facade=facade))

    result = mapping["start_memory_ingestion"](source_text="Yesterday I met Marco.")

    assert result.status == "ok"
    assert result.output == "Memory accepted."
    assert facade.calls[0][0] == "start_memory_ingestion"
    assert facade.calls[0][1].text == "Yesterday I met Marco."


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

    assert sorted(toolbox.tools_by_name) == ["request_graph_context_expansion"]
    assert result.status == "ok"
    assert result.data["matches"][0]["properties"]["id"] == "node-marco"
    assert ("search_nodes", "Marco") in graph.calls
