"""End-to-end composition of conversation entry and its memory-query child state."""

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from product.agentic.history import AgenticHistorySession
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.ai.ai_clients.protocols.protocol_chat import ChatRequest, ChatResponse, Msg
from product.application.composition import compose_conversation_memory
from product.application.memory_search import (
    MemorySearchFiltersDTO,
    MemorySearchNodeDTO,
    MemorySearchResultDTO,
    MemorySearchSeedDTO,
    MemorySearchService,
)
from product.application.references import ReferenceContext
from product.application.states.conversation_entry import ConversationEntryRequestDTO
from product.application.tools.conversation_entry import (
    IngestMemoryRequestDTO,
    IngestMemoryResultDTO,
)
from product.application.workflows import inspect_toolbox
from product.prompts import FilePromptTemplateSource, PromptRenderer, PromptService


class NestedScriptedProvider:
    name = "nested-scripted"

    def __init__(self, responses: list[ChatResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[list[Msg]] = []

    def make_client(self, _config: Any) -> object:
        return object()

    def describe(self, _config: Any) -> str:
        return "nested scripted provider"

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(
            [
                Msg(role=item.role, content=item.content, meta=dict(item.meta))
                for item in request.messages
            ]
        )
        return self.responses.pop(0)


class OnePersonMemoryBackend:
    def semantic_seeds(
        self,
        owner_id: str,
        query: str,
        *,
        filters: MemorySearchFiltersDTO,
        limit: int,
    ) -> list[MemorySearchSeedDTO]:
        return [
            MemorySearchSeedDTO(
                backend_id="alice-backend-id",
                label="Person",
                title="Alice Example",
                summary="A friend from university.",
            )
        ]

    def deterministic_seeds(
        self,
        owner_id: str,
        filters: MemorySearchFiltersDTO,
        *,
        limit: int,
    ) -> list[MemorySearchSeedDTO]:
        return []

    def hydrate(
        self,
        owner_id: str,
        seed_backend_ids: list[str],
        *,
        filters: MemorySearchFiltersDTO,
        depth: int,
        limit: int,
    ) -> MemorySearchResultDTO:
        return MemorySearchResultDTO(
            seed_backend_ids=["alice-backend-id"],
            nodes=[
                MemorySearchNodeDTO(
                    backend_id="alice-backend-id",
                    label="Person",
                    title="Alice Example",
                    summary="A friend from university.",
                )
            ],
        )


def _tool_call_response() -> ChatResponse:
    return ChatResponse(
        message=Msg(role="assistant", content=None),
        tool_calls=[
            SimpleNamespace(
                id="query-memory-call",
                function=SimpleNamespace(
                    name="query_memory",
                    arguments='{"goal":"Who is Alice?"}',
                ),
            )
        ],
    )


def _child_result_response() -> ChatResponse:
    return ChatResponse(
        message=Msg(
            role="assistant",
            content={
                "answer": "Alice is a friend from university.",
                "supporting_facts": [
                    {
                        "statement": "Alice is a university friend.",
                        "refs": ["node_0001"],
                    }
                ],
                "uncertainties": [],
            },
        )
    )


def _client(monkeypatch: Any) -> tuple[LLMInterfaceCore, NestedScriptedProvider]:
    provider = NestedScriptedProvider(
        [
            _tool_call_response(),
            _child_result_response(),
            ChatResponse(
                message=Msg(role="assistant", content="Alice is your friend from university.")
            ),
        ]
    )
    monkeypatch.setenv("BORIS_PROVIDER_DEFAULT", "openai")
    monkeypatch.setenv("BORIS_OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "product.ai.ai_clients.llm_core.llm_base.get_adapter",
        lambda *_args, **_kwargs: provider,
    )
    return (
        LLMInterfaceCore(
            logger=logging.getLogger("conversation-memory-composition-test"),
            base_path=Path.cwd(),
        ),
        provider,
    )


def test_memory_query_returns_as_matched_tool_output_before_parent_final_response(
    monkeypatch: Any,
) -> None:
    client, provider = _client(monkeypatch)
    templates_root = Path(__file__).parents[1] / "src" / "product" / "prompts" / "templates"
    prompt_service = PromptService(FilePromptTemplateSource(templates_root), PromptRenderer())
    reference_context = ReferenceContext()

    def ingest_memory(request: IngestMemoryRequestDTO) -> IngestMemoryResultDTO:
        return IngestMemoryResultDTO(result=f"Not used: {request.guidance}")

    composition = compose_conversation_memory(
        owner_id="owner-id",
        llm_client=client,
        history_session=AgenticHistorySession(),
        prompt_service=prompt_service,
        memory_search_service=MemorySearchService(OnePersonMemoryBackend()),
        reference_context=reference_context,
        ingest_memory=ingest_memory,
    )

    result = composition.conversation_entry.respond(
        ConversationEntryRequestDTO(user_message="Who is Alice?")
    )

    assert result.outcome == "completed"
    assert result.assistant_message.as_text() == "Alice is your friend from university."
    assert len(provider.requests) == 3
    parent_resume = provider.requests[2]
    tool_message = next(message for message in parent_resume if message.role == "tool")
    assert tool_message.meta["tool_call_id"] == "query-memory-call"
    tool_output = json.loads(str(tool_message.content))
    assert tool_output["status"] == "ok"
    assert tool_output["data"]["answer"] == "Alice is a friend from university."
    assert "Alice is your friend" not in str(tool_message.content)
    assert "alice-backend-id" not in str(tool_message.content)
    assert reference_context.ref_for_backend_id("alice-backend-id") == "node_0001"

    root_tools = inspect_toolbox(composition.conversation_entry.toolbox)
    query_tool = next(tool for tool in root_tools if tool.name == "query_memory")
    assert query_tool.child_state is not None
    assert query_tool.child_state.state_id == "memory_query"
    assert query_tool.child_state.toolbox_name == "memory_query"
    assert [tool.name for tool in query_tool.child_state.tools] == ["search_memory"]
