"""Functional preparation and execution of the grounded memory-query state."""

from copy import deepcopy
from pathlib import Path
from typing import Any

from product.agentic.history import AgenticHistorySession
from product.agentic.tools import AgenticToolInvocationContext, RegisteredTool
from product.ai.ai_clients.protocols.protocol_chat import ChatRequest, ChatResponse, Msg
from product.ai.ai_clients.protocols.protocol_tools import ToolDefinitionDTO
from product.application.references import ReferenceObjectKind, ReferenceResolutionStatus
from product.application.states import (
    MemoryQueryRequestDTO,
    MemoryQueryResultDTO,
    MemoryQueryState,
)
from product.application.tools.memory_search import (
    MemorySearchObjectDTO,
    MemorySearchRenderLevel,
    MemorySearchResultRenderer,
    MemorySearchToolInputDTO,
    MemorySearchToolResultDTO,
)
from product.prompts import FilePromptTemplateSource, PromptRenderer, PromptService


class IterativeMemoryQueryClient:
    """State-level fake optionally invoking searches before structured completion."""

    def __init__(self, follow_up_queries: list[str] | None = None) -> None:
        self.follow_up_queries = follow_up_queries or []
        self.requests: list[ChatRequest] = []
        self.mapping_names: list[str] = []

    def handle_params(
        self,
        *,
        system_prompt: str,
        chat_messages: list[Msg],
        **kwargs: Any,
    ) -> ChatRequest:
        return ChatRequest(
            model="test-model",
            messages=[Msg(role="system", content=system_prompt), *deepcopy(chat_messages)],
            tools=kwargs.get("tools"),
            params={"parallel_tool_calls": kwargs.get("parallel_tool_calls")},
        )

    def call(self, request: ChatRequest, mapping: dict[str, Any]) -> ChatResponse:
        self.requests.append(deepcopy(request))
        self.mapping_names = sorted(mapping)
        for query in self.follow_up_queries:
            mapping["search_memory"](semantic_query=query, limit=3)
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


def _prompt_service() -> PromptService:
    templates_root = Path(__file__).parents[1] / "src" / "product" / "prompts" / "templates"
    return PromptService(FilePromptTemplateSource(templates_root), PromptRenderer())


def _search_result() -> MemorySearchToolResultDTO:
    return MemorySearchToolResultDTO(
        seed_refs=["node_0001"],
        objects=[
            MemorySearchObjectDTO(
                ref="node_0001",
                object_kind=ReferenceObjectKind.NODE,
                label="Person",
                display_name="Alice Example",
                summary="A friend from university.",
                aliases=["Alice"],
                resolution_status=ReferenceResolutionStatus.EXISTING,
                temporal_summary="Known since 2018",
            )
        ],
    )


def _search_tool(
    calls: list[MemorySearchToolInputDTO],
    *,
    fail: bool = False,
) -> RegisteredTool[MemorySearchToolInputDTO, MemorySearchToolResultDTO]:
    def search(request: MemorySearchToolInputDTO) -> MemorySearchToolResultDTO:
        calls.append(request)
        if fail:
            raise ValueError("Memory search is temporarily unavailable.")
        return _search_result()

    return RegisteredTool(
        definition=ToolDefinitionDTO(
            name="search_memory",
            description="Search retained memory through model-safe references.",
            input_model=MemorySearchToolInputDTO,
        ),
        handler=search,
    )


def _child_context(
    history: AgenticHistorySession,
    current_message: str,
) -> AgenticToolInvocationContext:
    parent = history.start_state(
        "conversation_parent",
        [*history.master_history, Msg(role="user", content=current_message)],
    )
    return AgenticToolInvocationContext(
        history_session=history,
        parent_state_run_id=parent.state_run_id,
        parent_provider_call_id="parent-query-call",
    )


def test_memory_query_prepares_context_then_supports_iterative_searches() -> None:
    search_calls: list[MemorySearchToolInputDTO] = []
    client = IterativeMemoryQueryClient(["Alice relationships", "Alice university"])
    history = AgenticHistorySession([Msg(role="user", content="Earlier conversation.")])
    state = MemoryQueryState(
        client,  # type: ignore[arg-type]
        history,
        _prompt_service(),
        _search_tool(search_calls),
    )

    result = state.query(
        MemoryQueryRequestDTO(goal="Who is Alice?"),
        _child_context(history, "Current question about Alice."),
    )

    assert result.outcome == "completed"
    assert isinstance(result.structured_output, MemoryQueryResultDTO)
    assert [request.semantic_query for request in search_calls] == [
        "Who is Alice?",
        "Alice relationships",
        "Alice university",
    ]
    assert search_calls[0].neighborhood_depth == 1
    assert search_calls[0].limit == 10
    assert client.mapping_names == ["search_memory"]
    assert client.requests[0].params["parallel_tool_calls"] is False
    assert client.requests[0].messages[-1].as_text() == "Who is Alice?"
    system_prompt = client.requests[0].messages[0].as_text()
    assert "Alice Example" in system_prompt
    assert "person-a-id" not in system_prompt


def test_search_renderer_levels_are_caller_selected() -> None:
    renderer = MemorySearchResultRenderer()
    result = _search_result()

    compact = renderer.render(result, level=MemorySearchRenderLevel.COMPACT)
    standard = renderer.render(result, level=MemorySearchRenderLevel.STANDARD)
    detailed = renderer.render(result, level=MemorySearchRenderLevel.DETAILED)

    assert "A friend from university" not in compact
    assert "A friend from university" in standard
    assert "status=existing" not in standard
    assert "status=existing" in detailed
    assert "Known since 2018" in detailed


def test_initial_search_failure_still_reaches_the_agentic_session() -> None:
    search_calls: list[MemorySearchToolInputDTO] = []
    client = IterativeMemoryQueryClient()
    history = AgenticHistorySession()
    state = MemoryQueryState(
        client,  # type: ignore[arg-type]
        history,
        _prompt_service(),
        _search_tool(search_calls, fail=True),
    )

    result = state.query(
        MemoryQueryRequestDTO(goal="What do you remember?"),
        _child_context(history, "Please check my retained memories."),
    )

    assert result.outcome == "completed"
    assert len(search_calls) == 1
    system_prompt = client.requests[0].messages[0].as_text()
    assert "Initial search could not complete" in system_prompt
    assert "search_memory tool remains available" in system_prompt
