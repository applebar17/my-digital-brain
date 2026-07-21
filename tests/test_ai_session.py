from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from my_digital_brain.ai.models import ToolResult
from my_digital_brain.ai.schemas import ChatMessage, ProviderCallMetadata
from my_digital_brain.ai.session import (
    LLMCompletionRequest,
    LLMCompletionResult,
    LLMSessionAwaitingTool,
    LLMSessionCompleted,
    LLMSessionRequest,
    LLMSessionRunner,
)
from my_digital_brain.ai.tools import ToolBox
from my_digital_brain.ai.tools.base import build_tool_index


class Output(BaseModel):
    answer: str


class ScriptedTransport:
    def __init__(self, responses: list[ChatMessage]) -> None:
        self.responses = list(responses)
        self.requests: list[LLMCompletionRequest] = []

    def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
        self.requests.append(request)
        return LLMCompletionResult(
            assistant_message=self.responses.pop(0),
            metadata=ProviderCallMetadata.fake(model=request.model),
        )


def _toolbox(*names: str) -> ToolBox:
    tools = [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": name,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }
        for name in names
    ]
    return ToolBox(name="test", tools=tools, tools_by_name=build_tool_index(tools))


def _call(call_id: str, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments or {}),
        },
    }


def test_plain_text_session_completes_with_one_transcript() -> None:
    transport = ScriptedTransport([ChatMessage(role="assistant", content="hello")])

    result = LLMSessionRunner(transport).run(
        LLMSessionRequest(
            system_prompt="Be concise.", messages=[ChatMessage(role="user", content="Hi")]
        )
    )

    assert isinstance(result, LLMSessionCompleted)
    assert result.content == "hello"
    assert [message.role for message in result.messages] == ["system", "user", "assistant"]


def test_tools_and_structured_terminal_output_share_one_session() -> None:
    transport = ScriptedTransport(
        [
            ChatMessage(role="assistant", tool_calls=[_call("call-1", "record")]),
            ChatMessage(role="assistant", content='{"answer":"done"}'),
        ]
    )
    seen: list[str] = []

    result = LLMSessionRunner(transport).run(
        LLMSessionRequest(
            system_prompt="Use the tool.",
            messages=[ChatMessage(role="user", content="Do it")],
            output_schema=Output,
            toolbox=_toolbox("record"),
            tools_mapping={"record": lambda: seen.append("called")},
        )
    )

    assert isinstance(result, LLMSessionCompleted)
    assert result.parsed == Output(answer="done")
    assert seen == ["called"]
    assert transport.requests[0].tools
    assert transport.requests[0].response_format is not None
    assert transport.requests[1].tools
    assert len(result.messages) == 5


def test_tool_batch_is_not_split_when_it_exceeds_cap() -> None:
    transport = ScriptedTransport(
        [
            ChatMessage(
                role="assistant",
                tool_calls=[_call("call-1", "one"), _call("call-2", "two")],
            ),
            ChatMessage(role="assistant", content="finished"),
        ]
    )
    called: list[str] = []

    result = LLMSessionRunner(transport).run(
        LLMSessionRequest(
            system_prompt="Use tools.",
            toolbox=_toolbox("one", "two"),
            tools_mapping={
                "one": lambda: called.append("one"),
                "two": lambda: called.append("two"),
            },
            max_tool_calls=1,
        )
    )

    assert isinstance(result, LLMSessionCompleted)
    assert called == ["one", "two"]
    assert transport.requests[1].tools == []


def test_tool_errors_are_returned_in_the_transcript() -> None:
    transport = ScriptedTransport(
        [
            ChatMessage(role="assistant", tool_calls=[_call("call-1", "broken")]),
            ChatMessage(role="assistant", content="recovered"),
        ]
    )

    def broken_tool() -> None:
        raise ValueError("invalid backend input")

    result = LLMSessionRunner(transport).run(
        LLMSessionRequest(
            system_prompt="Use the backend tool.",
            toolbox=_toolbox("broken"),
            tools_mapping={"broken": broken_tool},
        )
    )

    assert isinstance(result, LLMSessionCompleted)
    assert result.content == "recovered"
    tool_message = result.messages[-2]
    assert tool_message.role == "tool"
    assert "tool_execution_error" in str(tool_message.content)


def test_pending_tool_can_resume_from_the_same_transcript() -> None:
    transport = ScriptedTransport(
        [
            ChatMessage(role="assistant", tool_calls=[_call("call-1", "ask")]),
            ChatMessage(role="assistant", content="resumed"),
        ]
    )

    first = LLMSessionRunner(transport).run(
        LLMSessionRequest(
            system_prompt="Ask when needed.",
            toolbox=_toolbox("ask"),
            tools_mapping={"ask": lambda: ToolResult(status="pending", output="question")},
            session_id="session-1",
        )
    )

    assert isinstance(first, LLMSessionAwaitingTool)
    tool_message = ChatMessage(
        role="tool",
        tool_call_id="call-1",
        content=ToolResult(status="ok", output="answer").model_dump_json(),
    )
    resumed = LLMSessionRunner(transport).run(
        LLMSessionRequest(
            system_prompt="Ask when needed.",
            messages=[*first.messages, tool_message],
            toolbox=_toolbox("ask"),
            tools_mapping={"ask": lambda: ToolResult(status="pending", output="question")},
            session_id="session-1",
            continuation=first.continuation,
        )
    )

    assert isinstance(resumed, LLMSessionCompleted)
    assert resumed.content == "resumed"
    assert resumed.session_id == "session-1"


def test_pending_batch_preserves_remaining_calls_until_resume() -> None:
    transport = ScriptedTransport(
        [
            ChatMessage(
                role="assistant",
                tool_calls=[_call("call-1", "ask"), _call("call-2", "record")],
            ),
            ChatMessage(role="assistant", content="all done"),
        ]
    )
    seen: list[str] = []

    first = LLMSessionRunner(transport).run(
        LLMSessionRequest(
            system_prompt="Resolve both calls.",
            toolbox=_toolbox("ask", "record"),
            tools_mapping={
                "ask": lambda: ToolResult(status="pending", output="question"),
                "record": lambda: seen.append("recorded"),
            },
            session_id="batch-session",
        )
    )

    assert isinstance(first, LLMSessionAwaitingTool)
    assert [call.call_id for call in first.continuation.remaining_tool_calls] == ["call-2"]
    resumed = LLMSessionRunner(transport).run(
        LLMSessionRequest(
            system_prompt="Resolve both calls.",
            messages=[
                *first.messages,
                ChatMessage(
                    role="tool",
                    tool_call_id="call-1",
                    content=ToolResult(status="ok", output="answered").model_dump_json(),
                ),
            ],
            toolbox=_toolbox("ask", "record"),
            tools_mapping={
                "ask": lambda: ToolResult(status="pending", output="question"),
                "record": lambda: seen.append("recorded"),
            },
            session_id="batch-session",
            continuation=first.continuation,
        )
    )

    assert isinstance(resumed, LLMSessionCompleted)
    assert seen == ["recorded"]
    assert resumed.content == "all done"


def test_invalid_structured_output_gets_one_repair_turn() -> None:
    transport = ScriptedTransport(
        [
            ChatMessage(role="assistant", content="invalid"),
            ChatMessage(role="assistant", content='{"answer":"fixed"}'),
        ]
    )

    result = LLMSessionRunner(transport).run(
        LLMSessionRequest(system_prompt="Return JSON.", output_schema=Output)
    )

    assert isinstance(result, LLMSessionCompleted)
    assert result.parsed == Output(answer="fixed")
    assert transport.requests[1].messages[-1].role == "user"
    assert "Repair your previous response" in str(transport.requests[1].messages[-1].content)
