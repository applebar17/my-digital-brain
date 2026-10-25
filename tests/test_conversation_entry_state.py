from copy import deepcopy
from pathlib import Path
from typing import Any

from product.agentic.history import AgenticHistorySession
from product.ai.ai_clients.protocols.protocol_chat import ChatRequest, ChatResponse, Msg
from product.application.states import ConversationEntryRequestDTO, ConversationEntryState
from product.application.tools import (
    ConversationCapabilityRequestDTO,
    ConversationCapabilityResultDTO,
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


def _prompt_service() -> PromptService:
    templates_root = Path(__file__).parents[1] / "src" / "product" / "prompts" / "templates"
    return PromptService(FilePromptTemplateSource(templates_root), PromptRenderer())


def test_conversation_entry_uses_selected_history_request_and_two_capabilities() -> None:
    query_calls: list[str] = []
    ingestion_calls: list[str] = []

    def query_memory(
        request: ConversationCapabilityRequestDTO,
    ) -> ConversationCapabilityResultDTO:
        query_calls.append(request.request)
        return ConversationCapabilityResultDTO(result="Query complete.")

    def ingest_memory(
        request: ConversationCapabilityRequestDTO,
    ) -> ConversationCapabilityResultDTO:
        ingestion_calls.append(request.request)
        return ConversationCapabilityResultDTO(result="Ingestion complete.")

    toolbox = build_conversation_entry_toolbox(
        query_memory=query_memory,
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
    assert query_calls == []
    assert ingestion_calls == []


def test_conversation_entry_toolbox_validates_and_dispatches_injected_handlers() -> None:
    received: list[ConversationCapabilityRequestDTO] = []

    def handler(
        request: ConversationCapabilityRequestDTO,
    ) -> ConversationCapabilityResultDTO:
        received.append(request)
        return ConversationCapabilityResultDTO(result="Handled.")

    toolbox = build_conversation_entry_toolbox(query_memory=handler, ingest_memory=handler)

    output = toolbox.tools_mapping["query_memory"](request="What do you remember?")

    assert output == ConversationCapabilityResultDTO(result="Handled.")
    assert received == [ConversationCapabilityRequestDTO(request="What do you remember?")]
