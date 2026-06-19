from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from my_digital_brain.agentic import (
    AgenticStateId,
    ConversationContext,
    MemoryQueryFoundationService,
    NeutralConversationMessage,
    QueryRetrievalPlanningContext,
    ToolResultStatus,
    default_state_configs,
)
from my_digital_brain.prompts import PromptRegistry


class FakeNode:
    def __init__(self, node_id: str) -> None:
        self.properties = {"id": node_id, "name": "Marco"}


class FakeGraphContextPackage(BaseModel):
    target: dict[str, Any]
    current_facts: list[dict[str, Any]]
    relationships: list[dict[str, Any]] = []
    relationship_contexts: list[dict[str, Any]] = []
    perceptions: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    notes: list[str] = []
    alias_map: dict[str, str] = {}


class FakeGraphQueryProvider:
    def __init__(self) -> None:
        self.search_queries: list[str | None] = []
        self.context_requests: list[tuple[str, bool, int, int]] = []

    def search_nodes(
        self,
        *,
        label: str | None = None,
        query: str | None = None,
        lifecycle_state: str | None = None,
        privacy_level: str | None = None,
        trust_level: str | None = None,
        limit: int = 25,
    ) -> list[FakeNode]:
        self.search_queries.append(query)
        return [FakeNode("node-marco")]

    def get_context_package(
        self,
        node_id: str,
        *,
        include_history: bool = True,
        timeline_limit: int = 20,
        relationship_limit: int = 50,
    ) -> FakeGraphContextPackage:
        self.context_requests.append(
            (node_id, include_history, timeline_limit, relationship_limit)
        )
        return FakeGraphContextPackage(
            target={"alias": "NODE_000001", "title": "Marco"},
            current_facts=[{"field": "name", "value": "Marco"}],
            relationship_contexts=[
                {
                    "alias": "RELCTX_000001",
                    "description": "University friend",
                    "emotional_summary": "Warm but distant now",
                }
            ],
            evidence=[
                {
                    "alias": "SOURCE_000001",
                    "title": "Chat memory",
                    "original_user_words": "Marco from university",
                }
            ],
            notes=["Retrieved from graph context package."],
            alias_map={"NODE_000001": "node-marco"},
        )


def test_memory_query_state_config_is_registered_with_read_only_tools() -> None:
    config = default_state_configs()[AgenticStateId.MEMORY_QUERY]

    assert config.prompt_id == "memory_query"
    assert "query_memory_context" in config.allowed_tools
    assert "get_context_package" in config.allowed_tools
    assert "request_user_clarification" not in config.allowed_tools
    assert "request_user_clarification" in config.forbidden_tools
    assert "execute_graph_write_plan" in config.forbidden_tools
    assert config.required_context_type == "QueryRetrievalPlanningContext"


def test_wave2_prompt_templates_are_registered() -> None:
    registry = PromptRegistry()

    assert "memory query state" in registry.load("memory_query").template
    assert "Plan graph retrieval" in registry.load("query_retrieval_planning").template
    assert "Generate a grounded answer" in registry.load("answer_generation").template


def test_query_foundation_without_graph_returns_no_memory_tool_context() -> None:
    service = MemoryQueryFoundationService()
    context = QueryRetrievalPlanningContext(
        question="What do I remember about Marco?",
        conversation=ConversationContext(
            current_message=NeutralConversationMessage.user(
                "What do I remember about Marco?"
            ),
        ),
    )

    result = service.run(context)

    assert result.answer_context is None
    assert result.tool_result.status == ToolResultStatus.FAILED.value
    assert result.tool_result.unresolved_questions == ["What do I remember about Marco?"]
    assert "not wired" in result.retrieval_result.uncertainty_notes[0]


def test_query_foundation_resolves_seed_and_builds_answer_context() -> None:
    graph = FakeGraphQueryProvider()
    service = MemoryQueryFoundationService(graph)
    context = QueryRetrievalPlanningContext(
        question="What do I remember about Marco?",
        conversation=ConversationContext(
            current_message=NeutralConversationMessage.user(
                "What do I remember about Marco?"
            ),
            compacted_summary="Earlier chat mentioned university friends.",
        ),
        entity_hints=["Marco"],
    )

    result = service.run(context)

    assert graph.search_queries == ["What do I remember about Marco?"]
    assert graph.context_requests == [("node-marco", True, 20, 50)]
    assert result.retrieval_result.seed_id == "node-marco"
    assert result.retrieval_result.seed_title == "Marco"
    assert result.answer_context is not None
    assert result.answer_context.context_package["alias_map"] == {
        "NODE_000001": "node-marco"
    }
    assert "Preserve emotional" in result.answer_context.evidence_rules[-1]
    assert result.tool_result.status == ToolResultStatus.OK.value
    assert result.tool_result.important_refs == ["node-marco"]


def test_query_foundation_accepts_explicit_seed_without_search() -> None:
    graph = FakeGraphQueryProvider()
    service = MemoryQueryFoundationService(graph)
    context = QueryRetrievalPlanningContext(
        question="Show me the timeline",
        conversation=ConversationContext(
            current_message=NeutralConversationMessage.user("Show me the timeline"),
        ),
        desired_view="timeline",
    )

    result = service.run(context, seed_id="node-explicit")

    assert graph.search_queries == []
    assert graph.context_requests == [("node-explicit", True, 20, 50)]
    assert result.retrieval_plan.seed_id == "node-explicit"
    assert result.retrieval_plan.metadata["desired_view"] == "timeline"
