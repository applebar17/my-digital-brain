from __future__ import annotations

import logging
import json
from threading import Barrier
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel, Field

from product.agentic.contracts import AgenticStateInvocationDTO
from product.agentic.history import AgenticHistorySession
from product.agentic.state import BaseAgenticState
from product.agentic.tools import RegisteredTool, ToolBox
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.ai.ai_clients.protocols.protocol_chat import ChatRequest, ChatResponse, Msg
from product.ai.ai_clients.protocols.protocol_tools import (
    ToolDefinitionDTO,
    ToolErrorDTO,
    ToolCallBatchPauseDTO,
    ToolCallResultDTO,
    ToolInteractionRequestDTO,
    ToolOutputDTO,
)


class ScriptedProvider:
    name = "scripted"

    def __init__(self, responses: list[ChatResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[list[Msg]] = []
        self.toolboxes: list[Any] = []
        self.request_params: list[dict[str, Any]] = []

    def make_client(self, _config: Any) -> object:
        return object()

    def describe(self, _config: Any) -> str:
        return "scripted provider"

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(
            [
                Msg(role=message.role, content=message.content, meta=dict(message.meta))
                for message in request.messages
            ]
        )
        self.toolboxes.append(request.tools)
        self.request_params.append(dict(request.params))
        return self.responses.pop(0)


def _tool_call(call_id: str, name: str, arguments: str = "{}") -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _assistant_tool_response(*calls: SimpleNamespace) -> ChatResponse:
    return ChatResponse(
        message=Msg(role="assistant", content=None),
        tool_calls=list(calls),
    )


def _assistant_final_response(text: str) -> ChatResponse:
    return ChatResponse(message=Msg(role="assistant", content=text))


def _request() -> ChatRequest:
    return ChatRequest(
        model="gpt-4o-mini",
        messages=[Msg(role="user", content="Do the requested work.")],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "configured_tools",
                    "description": "Tools made available to this session.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
        ],
        params={"model_kind": "chat", "parallel_tool_calls": True},
    )


def _client(
    monkeypatch: Any, responses: list[ChatResponse]
) -> tuple[LLMInterfaceCore, ScriptedProvider]:
    provider = ScriptedProvider(responses)
    monkeypatch.setenv("BORIS_PROVIDER_DEFAULT", "openai")
    monkeypatch.setenv("BORIS_OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "product.ai.ai_clients.llm_core.llm_base.get_adapter",
        lambda *_args, **_kwargs: provider,
    )
    client = LLMInterfaceCore(
        logger=logging.getLogger("tool-continuation-test"),
        base_path=Path.cwd(),
    )
    return client, provider


def test_tool_results_resume_the_provider_once_per_call_and_return_assistant_text(
    monkeypatch: Any,
) -> None:
    handler_calls: list[str] = []

    def lookup() -> dict[str, str]:
        handler_calls.append("lookup")
        return {"result": "found"}

    class ChildAgent:
        def __call__(self) -> dict[str, str]:
            handler_calls.append("child_agent")
            return {"result": "child completed"}

    def failing_handler() -> None:
        handler_calls.append("failing_handler")
        raise TypeError("handler input was not usable")

    def domain_failure() -> ToolOutputDTO:
        handler_calls.append("domain_failure")
        return ToolOutputDTO(
            status="error",
            error=ToolErrorDTO(code="not_found", message="The requested item was not found."),
        )

    client, provider = _client(
        monkeypatch,
        [
            _assistant_tool_response(
                _tool_call("call-lookup", "lookup"),
                _tool_call("call-child", "child_agent"),
                _tool_call("call-failure", "failing_handler"),
                _tool_call("call-failure", "failing_handler"),
                _tool_call("call-domain-failure", "domain_failure"),
            ),
            _assistant_final_response(
                "The lookup and child agent completed; one tool reported an error."
            ),
        ],
    )

    response = client.call(
        _request(),
        {
            "lookup": lookup,
            "child_agent": ChildAgent(),
            "failing_handler": failing_handler,
            "domain_failure": domain_failure,
        },
    )

    assert (
        response.message.content
        == "The lookup and child agent completed; one tool reported an error."
    )
    assert response.tool_calls == []
    assert sorted(handler_calls) == ["child_agent", "domain_failure", "failing_handler", "lookup"]

    transcript = provider.requests[1]
    assistant_tool_turn = next(
        message
        for message in transcript
        if message.role == "assistant" and "tool_calls" in message.meta
    )
    assert len(assistant_tool_turn.meta["tool_calls"]) == 4
    tool_messages = [message for message in transcript if message.role == "tool"]
    assert [message.meta["tool_call_id"] for message in tool_messages] == [
        "call-lookup",
        "call-child",
        "call-failure",
        "call-domain-failure",
    ]
    assert len({message.meta["tool_call_id"] for message in tool_messages}) == len(tool_messages)
    assert '"result":"found"' in str(tool_messages[0].content)
    assert '"result":"child completed"' in str(tool_messages[1].content)
    failed_output = json.loads(str(tool_messages[2].content))
    assert failed_output["status"] == "error"
    assert "TypeError: handler input was not usable" in failed_output["error"]["message"]
    assert "adjust the input or approach" in str(tool_messages[2].content)
    domain_failure_output = json.loads(str(tool_messages[3].content))
    assert domain_failure_output["status"] == "error"
    assert domain_failure_output["error"]["code"] == "not_found"
    assert domain_failure_output["error"]["message"] == "The requested item was not found."


def test_previously_seen_call_id_is_skipped_for_the_rest_of_the_session(
    monkeypatch: Any,
) -> None:
    handler_calls: list[str] = []

    def lookup() -> dict[str, str]:
        handler_calls.append("lookup")
        return {"result": "found"}

    client, provider = _client(
        monkeypatch,
        [
            _assistant_tool_response(_tool_call("session-call", "lookup")),
            _assistant_tool_response(_tool_call("session-call", "lookup")),
            _assistant_final_response("The earlier tool result is sufficient."),
        ],
    )

    response = client.call(_request(), {"lookup": lookup})

    assert response.message.content == "The earlier tool result is sufficient."
    assert handler_calls == ["lookup"]
    assert len(provider.requests) == 3
    assert [
        message.meta["tool_call_id"] for message in provider.requests[2] if message.role == "tool"
    ] == ["session-call"]


def test_invalid_tool_arguments_return_a_correlated_error_and_resume(
    monkeypatch: Any,
) -> None:
    handler_calls: list[str] = []

    def lookup(value: str) -> dict[str, str]:
        handler_calls.append(value)
        return {"result": value}

    client, provider = _client(
        monkeypatch,
        [
            _assistant_tool_response(_tool_call("invalid-call", "lookup", "{not-json")),
            _assistant_final_response(
                "The tool arguments were invalid, so I could not look it up."
            ),
        ],
    )

    response = client.call(_request(), {"lookup": lookup})

    assert response.message.content == "The tool arguments were invalid, so I could not look it up."
    assert handler_calls == []
    tool_message = next(message for message in provider.requests[1] if message.role == "tool")
    assert tool_message.meta["tool_call_id"] == "invalid-call"
    output = json.loads(str(tool_message.content))
    assert output["status"] == "error"
    assert output["error"]["code"] == "invalid_tool_arguments"


def test_typed_toolbox_handler_validation_error_returns_tool_result_and_resumes(
    monkeypatch: Any,
) -> None:
    class SearchInputDTO(BaseModel):
        query: str = Field(description="The phrase to search for.")

    class SearchOutputDTO(BaseModel):
        summary: str

    handler_calls: list[str] = []

    def search(input_dto: SearchInputDTO) -> SearchOutputDTO:
        handler_calls.append(input_dto.query)
        return SearchOutputDTO(summary=f"Found {input_dto.query}.")

    definition = ToolDefinitionDTO[SearchInputDTO](
        name="search",
        description="Search relevant memory.",
        input_model=SearchInputDTO,
    )
    toolbox = ToolBox("memory_query", [RegisteredTool(definition, search)])
    client, provider = _client(
        monkeypatch,
        [
            _assistant_tool_response(_tool_call("typed-call", "search", "{}")),
            _assistant_final_response("I could not search without a query."),
        ],
    )

    response = client.call(_request(), toolbox.tools_mapping)

    assert response.message.content == "I could not search without a query."
    assert handler_calls == []
    tool_message = next(message for message in provider.requests[1] if message.role == "tool")
    assert tool_message.meta["tool_call_id"] == "typed-call"
    output = json.loads(str(tool_message.content))
    assert output["status"] == "error"
    assert "ValidationError" in output["error"]["message"]


def test_unavailable_tool_mapping_returns_error_and_resumes(monkeypatch: Any) -> None:
    client, provider = _client(
        monkeypatch,
        [
            _assistant_tool_response(_tool_call("missing-handler-call", "missing_handler")),
            _assistant_final_response("That operation was unavailable; no action was taken."),
        ],
    )

    response = client.call(_request(), {})

    assert response.message.content == "That operation was unavailable; no action was taken."
    tool_message = next(message for message in provider.requests[1] if message.role == "tool")
    assert tool_message.meta["tool_call_id"] == "missing-handler-call"
    output = json.loads(str(tool_message.content))
    assert output["status"] == "error"
    assert output["error"]["code"] == "tool_handler_unavailable"


def test_tool_call_cap_returns_correlated_errors_then_requests_a_final_answer(
    monkeypatch: Any,
) -> None:
    executed: list[str] = []

    def run_tool(value: str) -> dict[str, str]:
        executed.append(value)
        return {"result": value}

    client, provider = _client(
        monkeypatch,
        [
            _assistant_tool_response(
                _tool_call("call-1", "run_tool", '{"value":"one"}'),
                _tool_call("call-2", "run_tool", '{"value":"two"}'),
                _tool_call("call-3", "run_tool", '{"value":"three"}'),
            ),
            _assistant_tool_response(_tool_call("call-after-cap", "run_tool")),
            _assistant_final_response("Completed within the tool-call limit."),
        ],
    )
    client.tool_call_cap = 1

    response = client.call(_request(), {"run_tool": run_tool})

    assert response.message.content == "Completed within the tool-call limit."
    assert response.message.role == "assistant"
    assert response.tool_calls == []
    assert executed == ["one"]

    final_request = provider.requests[1]
    tool_messages = [message for message in final_request if message.role == "tool"]
    assert [message.meta["tool_call_id"] for message in tool_messages] == [
        "call-1",
        "call-2",
        "call-3",
    ]
    assert '"result":"one"' in str(tool_messages[0].content)
    assert "tool-call limit (1) was reached" in str(tool_messages[1].content)
    assert "tool-call limit (1) was reached" in str(tool_messages[2].content)
    assert provider.requests[2][-1].meta["tool_call_id"] == "call-after-cap"
    assert "tool-call limit (1) was reached" in str(provider.requests[2][-1].content)
    assert provider.toolboxes[0] is not None
    assert provider.toolboxes[1] is None
    assert provider.toolboxes[2] is None
    assert "parallel_tool_calls" not in provider.request_params[1]
    assert final_request[0].role == "user"


def test_returned_tool_batch_executes_concurrently_and_preserves_call_pairing(
    monkeypatch: Any,
) -> None:
    barrier = Barrier(3, timeout=2)

    def handler(value: str) -> dict[str, str]:
        barrier.wait()
        return {"value": value}

    client, provider = _client(
        monkeypatch,
        [
            _assistant_tool_response(
                _tool_call("call-a", "work", '{"value":"a"}'),
                _tool_call("call-b", "work", '{"value":"b"}'),
                _tool_call("call-c", "work", '{"value":"c"}'),
            ),
            _assistant_final_response("All three calls completed."),
        ],
    )

    response = client.call(_request(), {"work": handler})

    assert response.message.content == "All three calls completed."
    tool_messages = [message for message in provider.requests[1] if message.role == "tool"]
    assert [message.meta["tool_call_id"] for message in tool_messages] == [
        "call-a",
        "call-b",
        "call-c",
    ]
    assert [json.loads(str(message.content))["data"]["value"] for message in tool_messages] == [
        "a",
        "b",
        "c",
    ]


def test_parallel_batch_waits_for_every_external_answer_before_one_next_call(
    monkeypatch: Any,
) -> None:
    class QuestionPacket(BaseModel):
        question: str

    def ask_first() -> ToolInteractionRequestDTO[QuestionPacket]:
        return ToolInteractionRequestDTO[QuestionPacket](
            interaction_packet=QuestionPacket(question="Which first item?")
        )

    def lookup() -> dict[str, str]:
        return {"item": "second item found"}

    def ask_second() -> ToolInteractionRequestDTO[QuestionPacket]:
        return ToolInteractionRequestDTO[QuestionPacket](
            interaction_packet=QuestionPacket(question="Which second item?")
        )

    toolbox = {"ask_first": ask_first, "lookup": lookup, "ask_second": ask_second}
    client, provider = _client(
        monkeypatch,
        [
            _assistant_tool_response(
                _tool_call("call-first", "ask_first"),
                _tool_call("call-lookup", "lookup"),
                _tool_call("call-second", "ask_second"),
            ),
            _assistant_final_response("The full batch is now available."),
        ],
    )
    request = _request()

    paused = client.call(request, toolbox)

    assert isinstance(paused, ToolCallBatchPauseDTO)
    assert len(provider.requests) == 1
    assert [call.provider_call_id for call in paused.calls] == [
        "call-first",
        "call-lookup",
        "call-second",
    ]
    assert paused.calls[0].interaction_request.interaction_packet.question == "Which first item?"
    assert paused.calls[1].tool_output.data == {"item": "second item found"}
    assert paused.calls[2].interaction_request.interaction_packet.question == "Which second item?"

    partially_resumed = client.resume_tool_batch(
        request,
        paused,
        [
            ToolCallResultDTO(
                provider_call_id="call-first",
                tool_output=ToolOutputDTO(status="ok", data={"answer": "first answer"}),
            )
        ],
        toolbox,
    )
    assert isinstance(partially_resumed, ToolCallBatchPauseDTO)
    assert len(provider.requests) == 1

    completed = client.resume_tool_batch(
        request,
        partially_resumed,
        [
            ToolCallResultDTO(
                provider_call_id="call-second",
                tool_output=ToolOutputDTO(status="ok", data={"answer": "second answer"}),
            )
        ],
        toolbox,
    )

    assert isinstance(completed, ChatResponse)
    assert completed.message.content == "The full batch is now available."
    assert len(provider.requests) == 2
    tool_messages = [message for message in provider.requests[1] if message.role == "tool"]
    assert [message.meta["tool_call_id"] for message in tool_messages] == [
        "call-first",
        "call-lookup",
        "call-second",
    ]
    assert [json.loads(str(message.content))["status"] for message in tool_messages] == [
        "ok",
        "ok",
        "ok",
    ]


def test_output_preparation_failure_still_sends_one_error_for_every_batch_call(
    monkeypatch: Any,
) -> None:
    client, provider = _client(
        monkeypatch,
        [
            _assistant_tool_response(
                _tool_call("call-a", "work"),
                _tool_call("call-b", "work"),
            ),
            _assistant_final_response("Both calls have results."),
        ],
    )
    def fail_clamp(*_args: Any) -> str:
        raise RuntimeError("clamp failed")

    client._tool_call_batch_runtime._clamp_for_model = fail_clamp

    response = client.call(_request(), {"work": lambda: {"done": True}})

    assert response.message.content == "Both calls have results."
    tool_messages = [message for message in provider.requests[1] if message.role == "tool"]
    assert [message.meta["tool_call_id"] for message in tool_messages] == ["call-a", "call-b"]
    assert [json.loads(str(message.content))["error"]["code"] for message in tool_messages] == [
        "tool_output_preparation_failed",
        "tool_output_preparation_failed",
    ]


def test_parent_state_invokes_child_state_as_tool_and_receives_matched_output(
    monkeypatch: Any,
) -> None:
    class ChildInputDTO(BaseModel):
        query: str = Field(description="The focused question for the child state.")

    class ChildOutputDTO(BaseModel):
        answer: str = Field(description="The child state's answer.")

    llm_client, provider = _client(
        monkeypatch,
        [
            _assistant_tool_response(
                _tool_call("call-memory-query-1", "query_memory", '{"query":"What about Marco?"}')
            ),
            _assistant_final_response('{"answer":"Marco was your university friend."}'),
            _assistant_final_response("Marco was your university friend."),
        ],
    )
    history_session = AgenticHistorySession()
    child_state = BaseAgenticState("memory_query", llm_client, history_session)

    def invoke_child(input_dto: ChildInputDTO) -> ChildOutputDTO:
        child_result = child_state.invoke(
            AgenticStateInvocationDTO(
                system_prompt="Answer the focused memory query.",
                request=input_dto.query,
                response_model=ChildOutputDTO,
            )
        )
        assert child_result.outcome == "completed"
        assert isinstance(child_result.structured_output, ChildOutputDTO)
        return child_result.structured_output

    query_tool = RegisteredTool[ChildInputDTO, ChildOutputDTO](
        definition=ToolDefinitionDTO[ChildInputDTO](
            name="query_memory",
            description="Ask the memory-query child state a focused question.",
            input_model=ChildInputDTO,
        ),
        handler=invoke_child,
    )
    parent_state = BaseAgenticState("conversation_entry", llm_client, history_session)

    parent_result = parent_state.invoke(
        AgenticStateInvocationDTO(
            system_prompt="Use query_memory when the user asks about a remembered fact.",
            request="What do I remember about Marco?",
            toolbox=ToolBox("conversation_entry", [query_tool]),
        )
    )

    assert parent_result.outcome == "completed"
    assert parent_result.assistant_message.content == "Marco was your university friend."
    assert [messages[-1].content for messages in provider.requests[:2]] == [
        "What do I remember about Marco?",
        "What about Marco?",
    ]

    parent_resume_messages = provider.requests[2]
    child_tool_output = next(message for message in parent_resume_messages if message.role == "tool")
    assert child_tool_output.meta["tool_call_id"] == "call-memory-query-1"
    assert json.loads(child_tool_output.content) == {
        "status": "ok",
        "data": {"answer": "Marco was your university friend."},
    }
