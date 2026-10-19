from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.ai.ai_clients.protocols.protocol_chat import ChatRequest, ChatResponse, Msg


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

    client, provider = _client(
        monkeypatch,
        [
            _assistant_tool_response(
                _tool_call("call-lookup", "lookup"),
                _tool_call("call-child", "child_agent"),
                _tool_call("call-failure", "failing_handler"),
                _tool_call("call-failure", "failing_handler"),
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
        },
    )

    assert (
        response.message.content
        == "The lookup and child agent completed; one tool reported an error."
    )
    assert response.tool_calls == []
    assert handler_calls == ["lookup", "child_agent", "failing_handler"]

    transcript = provider.requests[1]
    assistant_tool_turn = next(
        message
        for message in transcript
        if message.role == "assistant" and "tool_calls" in message.meta
    )
    assert len(assistant_tool_turn.meta["tool_calls"]) == 3
    tool_messages = [message for message in transcript if message.role == "tool"]
    assert [message.meta["tool_call_id"] for message in tool_messages] == [
        "call-lookup",
        "call-child",
        "call-failure",
    ]
    assert len({message.meta["tool_call_id"] for message in tool_messages}) == len(tool_messages)
    assert '"result":"found"' in str(tool_messages[0].content)
    assert '"result":"child completed"' in str(tool_messages[1].content)
    assert "TypeError: handler input was not usable" in str(tool_messages[2].content)
    assert "adjust the input or approach" in str(tool_messages[2].content)


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
