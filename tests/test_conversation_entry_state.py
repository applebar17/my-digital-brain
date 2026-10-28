from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from product.agentic.contracts import AgenticStateResultDTO
from product.agentic.history import AgenticHistorySession
from product.agentic.tools import AgenticToolInvocationContext, ToolBox
from product.ai.ai_clients.protocols.protocol_chat import ChatRequest, ChatResponse, Msg
from product.ai.ai_clients.protocols.protocol_tools import ToolCallContextDTO
from product.application.states.conversation_entry import (
    ConversationEntryRequestDTO,
    ConversationEntryState,
)
from product.application.states.memory_query import (
    MemoryQueryRequestDTO,
    MemoryQueryResultDTO,
)
from product.application.tools.conversation_entry import (
    IngestMemoryRequestDTO,
    IngestMemoryResultDTO,
    build_conversation_entry_toolbox,
)
from product.prompts import FilePromptTemplateSource, PromptRenderer, PromptService


class RecordingLLMClient:
    """Focused state test client recording the request and executable mapping."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.requests: list[ChatRequest] = []
        self.tool_names: list[str] = []

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
        self.tool_names = sorted(mapping)
        return ChatResponse(message=Msg(role="assistant", content=self.response))


class FakeMemoryQueryState:
    state_id = "memory_query"
    toolbox = ToolBox("memory_query", [])

    def __init__(self) -> None:
        self.requests: list[MemoryQueryRequestDTO] = []

    def query(
        self,
        request: MemoryQueryRequestDTO,
        invocation_context: AgenticToolInvocationContext,
    ) -> AgenticStateResultDTO[BaseModel]:
        self.requests.append(request)
        invocation_context.inherited_history()
        return AgenticStateResultDTO[BaseModel](
            outcome="completed",
            structured_output=MemoryQueryResultDTO(
                answer="Query complete.",
                supporting_facts=[],
                uncertainties=[],
            ),
        )


def _prompt_service() -> PromptService:
    templates_root = Path(__file__).parents[1] / "src" / "product" / "prompts" / "templates"
    return PromptService(FilePromptTemplateSource(templates_root), PromptRenderer())


def test_conversation_entry_uses_selected_history_request_and_two_capabilities() -> None:
    ingestion_calls: list[str] = []
    memory_query = FakeMemoryQueryState()

    def ingest_memory(
        request: IngestMemoryRequestDTO,
    ) -> IngestMemoryResultDTO:
        ingestion_calls.append(request.guidance or "")
        return IngestMemoryResultDTO(result="Ingestion complete.")

    toolbox = build_conversation_entry_toolbox(
        memory_query_state=memory_query,  # type: ignore[arg-type]
        ingest_memory=ingest_memory,
    )
    client = RecordingLLMClient("I can help with that.")
    history = [Msg(role="user", content="Earlier message.")]
    state = ConversationEntryState(
        client,  # type: ignore[arg-type]
        AgenticHistorySession(history),
        _prompt_service(),
        toolbox,
    )

    result = state.respond(ConversationEntryRequestDTO(user_message="Current message."))

    assert result.outcome == "completed"
    assert result.assistant_message.as_text() == "I can help with that."
    assert client.tool_names == ["ingest_memory", "query_memory"]
    assert [message.role for message in client.requests[0].messages] == [
        "system",
        "user",
        "user",
    ]
    assert client.requests[0].messages[-1].as_text() == "Current message."
    assert client.requests[0].params["parallel_tool_calls"] is True
    assert "user-facing conversation agent" in client.requests[0].messages[0].as_text()
    assert memory_query.requests == []
    assert ingestion_calls == []


def test_conversation_entry_toolbox_validates_and_dispatches_injected_handlers() -> None:
    received: list[IngestMemoryRequestDTO] = []
    memory_query = FakeMemoryQueryState()

    def handler(
        request: IngestMemoryRequestDTO,
    ) -> IngestMemoryResultDTO:
        received.append(request)
        return IngestMemoryResultDTO(result="Handled.")

    toolbox = build_conversation_entry_toolbox(
        memory_query_state=memory_query,  # type: ignore[arg-type]
        ingest_memory=handler,
    )

    history_session = AgenticHistorySession()
    parent = history_session.start_state(
        "conversation_parent",
        [Msg(role="user", content="What do you remember?")],
    )
    mapping = toolbox.bind_to_state(history_session, parent.state_run_id)
    query_output = mapping["query_memory"].invoke_for_tool_call(
        ToolCallContextDTO(provider_call_id="query-call", tool_name="query_memory"),
        goal="What do you remember?",
    )
    ingestion_output = mapping["ingest_memory"].invoke_for_tool_call(
        ToolCallContextDTO(provider_call_id="ingest-call", tool_name="ingest_memory"),
        guidance="Remember this.",
    )

    assert query_output == MemoryQueryResultDTO(
        answer="Query complete.",
        supporting_facts=[],
        uncertainties=[],
    )
    assert ingestion_output == IngestMemoryResultDTO(result="Handled.")
    assert received == [IngestMemoryRequestDTO(guidance="Remember this.")]
