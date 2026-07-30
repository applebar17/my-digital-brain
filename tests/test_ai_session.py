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
    continuation_with_tool_results,
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
    continuation = continuation_with_tool_results(
        first.continuation,
        {"call-1": ToolResult(status="ok", output="answer")},
    )
    resumed = LLMSessionRunner(transport).run(
        LLMSessionRequest(
            system_prompt="Ask when needed.",
            messages=continuation.messages,
            toolbox=_toolbox("ask"),
            tools_mapping={"ask": lambda: ToolResult(status="pending", output="question")},
            session_id="session-1",
            continuation=continuation,
        )
    )

    assert isinstance(resumed, LLMSessionCompleted)
    assert resumed.content == "resumed"
    assert resumed.session_id == "session-1"


def test_multiple_pending_tools_keep_chat_completion_transcript_valid() -> None:
    transport = ScriptedTransport(
        [
            ChatMessage(
                role="assistant",
                tool_calls=[_call("call-1", "ask"), _call("call-2", "ask")],
            ),
            ChatMessage(role="assistant", content="all clarifications answered"),
        ]
    )

    def ask() -> ToolResult:
        return ToolResult(status="pending", output="question")

    request = LLMSessionRequest(
        system_prompt="Ask both questions.",
        toolbox=_toolbox("ask"),
        tools_mapping={"ask": ask},
        session_id="multi-pending",
    )
    first = LLMSessionRunner(transport).run(request)
    assert isinstance(first, LLMSessionAwaitingTool)
    assert [call.call_id for call in first.continuation.pending_tool_calls] == [
        "call-1",
        "call-2",
    ]

    second_continuation = continuation_with_tool_results(
        first.continuation,
        {
            "call-1": ToolResult(status="ok", output="first answer"),
            "call-2": ToolResult(status="ok", output="second answer"),
        },
    )
    second = LLMSessionRunner(transport).run(
        request.model_copy(
            update={
                "messages": second_continuation.messages,
                "continuation": second_continuation,
            }
        )
    )
    assert isinstance(second, LLMSessionCompleted)
    assert second.content == "all clarifications answered"
    tool_messages = [message for message in second.messages if message.role == "tool"]
    assert {message.tool_call_id for message in tool_messages} == {"call-1", "call-2"}


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
    assert first.continuation.pending_tool_calls[0].call_id == "call-1"
    assert seen == ["recorded"]
    resumed_continuation = continuation_with_tool_results(
        first.continuation,
        {"call-1": ToolResult(status="ok", output="answered")},
    )
    resumed = LLMSessionRunner(transport).run(
        LLMSessionRequest(
            system_prompt="Resolve both calls.",
            messages=resumed_continuation.messages,
            toolbox=_toolbox("ask", "record"),
            tools_mapping={
                "ask": lambda: ToolResult(status="pending", output="question"),
                "record": lambda: seen.append("recorded"),
            },
            session_id="batch-session",
            continuation=resumed_continuation,
        )
    )

    assert isinstance(resumed, LLMSessionCompleted)
    assert seen == ["recorded"]
    assert resumed.content == "all done"


def test_six_parallel_question_calls_are_rejected_without_dropping_calls() -> None:
    calls = [_call(f"question-{index}", "question") for index in range(6)]
    transport = ScriptedTransport(
        [
            ChatMessage(role="assistant", tool_calls=calls),
            ChatMessage(role="assistant", content="I will split the questions."),
        ]
    )

    result = LLMSessionRunner(transport).run(
        LLMSessionRequest(
            system_prompt="Ask questions.",
            toolbox=_toolbox("question"),
            tools_mapping={
                "question": lambda: ToolResult(
                    status="pending",
                    output="question",
                    data={"interaction_group": "clarification_questions"},
                )
            },
        )
    )

    assert isinstance(result, LLMSessionCompleted)
    errors = [message for message in result.messages if message.role == "tool"]
    assert len(errors) == 6
    assert all("clarification_packet_limit_exceeded" in message.content for message in errors)


def test_parallel_question_calls_share_one_pending_packet() -> None:
    packet = {
        "frame_id": "frame-1",
        "origin_state_id": "clarification_agent",
        "reason": "Resolve the supplied doubt.",
        "questions": [
            {
                "question": "Who is Amos?",
                "kind": "missing_attribute",
                "response_mode": "text_or_audio",
            }
        ],
    }
    transport = ScriptedTransport(
        [
            ChatMessage(
                role="assistant",
                tool_calls=[_call("question-1", "question"), _call("question-2", "question")],
            )
        ]
    )

    result = LLMSessionRunner(transport).run(
        LLMSessionRequest(
            system_prompt="Ask questions.",
            toolbox=_toolbox("question"),
            tools_mapping={
                "question": lambda: ToolResult(
                    status="pending",
                    output="question",
                    data={
                        "interaction_group": "clarification_questions",
                        "clarification_packet": packet,
                    },
                )
            },
        )
    )

    assert isinstance(result, LLMSessionAwaitingTool)
    assert len(result.continuation.pending_tool_calls) == 2
    assert len(result.continuation.pending_interaction["clarification_packet"]["questions"]) == 2
    assert result.continuation.pending_interaction["clarification_packet"][
        "tool_call_id"
    ].startswith("clarification-group-")


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
