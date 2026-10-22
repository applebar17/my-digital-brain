from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel

from product.agentic.contracts import (
    AgenticStageConfigurationDTO,
    AgenticStateInvocationDTO,
    AgenticStateResumeDTO,
    PausedStateContinuationDTO,
    PlanArtifact,
    ReasoningArtifact,
    ToolCallBatchItemDTO,
    ToolCallBatchPauseDTO,
    ToolCallResultDTO,
    ToolInteractionRequestDTO,
)
from product.agentic.history import AgenticHistorySession
from product.agentic.state import BaseAgenticState
from product.ai.ai_clients.protocols.protocol_chat import ChatRequest, ChatResponse, Msg
from product.ai.ai_clients.protocols.protocol_tools import ToolOutputDTO


class FakeLLMClient:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[ChatRequest] = []
        self.responses: list[list[ToolCallResultDTO]] = []

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

    def call(self, request: ChatRequest, _mapping: Any) -> Any:
        self.requests.append(deepcopy(request))
        return self.outcomes.pop(0)

    def resume_tool_batch(
        self,
        request: ChatRequest,
        _batch: ToolCallBatchPauseDTO[BaseModel],
        results: list[ToolCallResultDTO],
        _mapping: Any,
    ) -> Any:
        self.requests.append(deepcopy(request))
        self.responses.append(results)
        return self.outcomes.pop(0)


def test_invocation_uses_caller_history_and_parses_terminal_structured_output() -> None:
    class AnswerDTO(BaseModel):
        answer: str

    selected_history = [Msg(role="user", content="Earlier context.")]
    client = FakeLLMClient(
        [ChatResponse(message=Msg(role="assistant", content={"answer": "Done."}))]
    )
    session = AgenticHistorySession()
    state = BaseAgenticState("answer_state", client, session)  # type: ignore[arg-type]

    result = state.invoke(
        AgenticStateInvocationDTO(
            system_prompt="You are concise.",
            selected_history=selected_history,
            request="Answer the question.",
            response_model=AnswerDTO,
            parallel_tool_calls=True,
        )
    )

    assert result.outcome == "completed"
    assert isinstance(result.structured_output, AnswerDTO)
    assert result.structured_output.answer == "Done."
    sent = client.requests[0]
    assert [message.role for message in sent.messages] == ["system", "user", "user"]
    assert sent.messages[0].content == "You are concise."
    assert sent.messages[-1].content == "Answer the question."
    assert sent.params["parallel_tool_calls"] is True
    assert selected_history == [Msg(role="user", content="Earlier context.")]


def test_state_resumes_same_run_after_all_batch_outputs_are_available() -> None:
    class QuestionDTO(BaseModel):
        question: str

    pause = ToolCallBatchPauseDTO[QuestionDTO](
        calls=[
            ToolCallBatchItemDTO[QuestionDTO](
                provider_call_id="call-question",
                tool_name="ask_user",
                interaction_request=ToolInteractionRequestDTO[QuestionDTO](
                    interaction_packet=QuestionDTO(question="Which one?")
                ),
            )
        ],
        tool_calls_processed=1,
        tool_call_cap=8,
        seen_call_ids=["call-question"],
    )
    client = FakeLLMClient(
        [pause, ChatResponse(message=Msg(role="assistant", content="Thanks, continuing."))]
    )
    session = AgenticHistorySession()
    state = BaseAgenticState("question_state", client, session)  # type: ignore[arg-type]

    paused = state.invoke(
        AgenticStateInvocationDTO(
            system_prompt="Ask only necessary questions.",
            request="Resolve the ambiguity.",
        )
    )

    assert paused.outcome == "awaiting_input"
    continuation = paused.continuation
    assert isinstance(continuation, PausedStateContinuationDTO[QuestionDTO])
    run_id = continuation.state_history.state_run_id
    assert session.get_state(run_id).state_id == "question_state"

    completed = state.resume(
        AgenticStateResumeDTO[QuestionDTO](
            continuation=continuation,
            tool_results=[
                ToolCallResultDTO(
                    provider_call_id="call-question",
                    tool_output=ToolOutputDTO(status="ok", data={"answer": "The first one."}),
                )
            ],
        )
    )

    assert completed.outcome == "completed"
    assert completed.assistant_message.content == "Thanks, continuing."
    assert client.responses[0][0].provider_call_id == "call-question"
    assert client.requests[0].messages[-1].content == "Resolve the ambiguity."
    assert client.requests[1].messages == client.requests[0].messages
    try:
        session.get_state(run_id)
    except ValueError:
        pass
    else:
        raise AssertionError("Completed state history should be released.")


def test_reasoning_then_planning_then_main_passes_only_typed_artifacts_forward() -> None:
    client = FakeLLMClient(
        [
            ChatResponse(
                message=Msg(
                    role="assistant",
                    content={
                        "summary": "The date references differ.",
                        "impacts": ["Keep the dates aligned."],
                        "inconsistencies": [],
                        "information_gaps": [],
                        "constraints_or_gates": [],
                    },
                )
            ),
            ChatResponse(
                message=Msg(
                    role="assistant",
                    content={"goal": "Resolve the request", "planned_actions": []},
                )
            ),
            ChatResponse(message=Msg(role="assistant", content="Completed.")),
        ]
    )
    state = BaseAgenticState("staged_state", client, AgenticHistorySession())  # type: ignore[arg-type]

    result = state.invoke(
        AgenticStateInvocationDTO(
            system_prompt="Main instructions.",
            selected_history=[Msg(role="user", content="Earlier context.")],
            request="Resolve the request.",
            reasoning_stage=AgenticStageConfigurationDTO(
                system_prompt="Analyze context.", response_model=ReasoningArtifact
            ),
            planning_stage=AgenticStageConfigurationDTO(
                system_prompt="Plan the work.", response_model=PlanArtifact
            ),
        )
    )

    assert result.outcome == "completed"
    assert [request.messages[0].content for request in client.requests[:2]] == [
        "Analyze context.",
        "Plan the work.",
    ]
    assert client.requests[2].messages[0].content.startswith("Main instructions.")
    assert "Keep the dates aligned." in client.requests[1].messages[-1].content
    assert client.requests[2].messages[-1].content == "Resolve the request."
    assert "planned_actions" in client.requests[2].messages[0].content
    assert all(
        "summary" not in message.as_text()
        for message in client.requests[2].messages
        if message.role == "assistant"
    )


def test_planning_pause_resumes_planning_before_starting_main_call() -> None:
    class QuestionDTO(BaseModel):
        question: str

    pause = ToolCallBatchPauseDTO[QuestionDTO](
        calls=[
            ToolCallBatchItemDTO[QuestionDTO](
                provider_call_id="call-plan-question",
                tool_name="ask_user",
                interaction_request=ToolInteractionRequestDTO[QuestionDTO](
                    interaction_packet=QuestionDTO(question="Which date should I use?")
                ),
            ),
            ToolCallBatchItemDTO[QuestionDTO](
                provider_call_id="call-plan-confirmation",
                tool_name="ask_user",
                interaction_request=ToolInteractionRequestDTO[QuestionDTO](
                    interaction_packet=QuestionDTO(question="Which calendar year?")
                ),
            ),
        ],
        tool_calls_processed=2,
        tool_call_cap=8,
        seen_call_ids=["call-plan-question", "call-plan-confirmation"],
    )
    client = FakeLLMClient(
        [
            pause,
            ChatResponse(
                message=Msg(
                    role="assistant",
                    content={"goal": "Plan the update", "planned_actions": []},
                )
            ),
            ChatResponse(message=Msg(role="assistant", content="Update completed.")),
        ]
    )
    session = AgenticHistorySession()
    state = BaseAgenticState("planning_state", client, session)  # type: ignore[arg-type]
    stage = AgenticStageConfigurationDTO(
        system_prompt="Create a plan; ask if required information is missing.",
        response_model=PlanArtifact,
    )

    paused = state.invoke(
        AgenticStateInvocationDTO(
            system_prompt="Main instructions.",
            request="Plan the update.",
            planning_stage=stage,
        )
    )

    assert paused.outcome == "awaiting_input"
    continuation = paused.continuation
    assert continuation.execution_stage == "planning"
    assert continuation.main_state_history.messages[0].as_text() == "Main instructions."
    assert len(client.requests) == 1  # No main-model call while the question is unanswered.

    completed = state.resume(
        AgenticStateResumeDTO[QuestionDTO](
            continuation=continuation,
            tool_results=[
                ToolCallResultDTO(
                    provider_call_id="call-plan-question",
                    tool_output=ToolOutputDTO(status="ok", data={"answer": "2 June"}),
                ),
                ToolCallResultDTO(
                    provider_call_id="call-plan-confirmation",
                    tool_output=ToolOutputDTO(status="ok", data={"answer": "2026"}),
                ),
            ],
            planning_stage=stage,
        )
    )

    assert completed.outcome == "completed"
    assert len(client.requests) == 3  # Resume planning to its artifact, then call main once.
    assert [result.provider_call_id for result in client.responses[0]] == [
        "call-plan-question",
        "call-plan-confirmation",
    ]
    assert client.requests[1].messages[0].content == stage.system_prompt
    assert client.requests[2].messages[0].content.startswith("Main instructions.")
    assert "planned_actions" in client.requests[2].messages[0].content
    assert client.requests[2].messages[-1].content == "Plan the update."
