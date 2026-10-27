"""Nested clarification child pause and parent continuation behavior."""

import json
import logging
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from product.agentic.contracts import AgenticStateInvocationDTO, AgenticStateResumeDTO
from product.agentic.history import AgenticHistorySession
from product.agentic.state import BaseAgenticState
from product.agentic.tools import ToolBox
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.ai.ai_clients.protocols.protocol_chat import ChatRequest, ChatResponse, Msg
from product.application.interactions import (
    InteractionContinuationStore,
    ParentToolResumeDTO,
    QuestionMode,
    UserInteractionService,
    UserQuestionAnswerDTO,
)
from product.application.states.clarification import ClarificationState
from product.application.tools.clarification import build_clarification_agent_tool
from product.application.tools.user_interaction import build_ask_user_tool
from product.prompts import FilePromptTemplateSource, PromptRenderer, PromptService


def _tool_call(call_id: str, name: str, arguments: str) -> ChatResponse:
    return ChatResponse(
        message=Msg(role="assistant", content=None),
        tool_calls=[
            SimpleNamespace(
                id=call_id,
                function=SimpleNamespace(name=name, arguments=arguments),
            )
        ],
    )


class NestedClarificationProvider:
    name = "nested-clarification-scripted"

    def __init__(self, *, clarification_outcome: str, parent_message: str) -> None:
        self.requests: list[list[Msg]] = []
        self.responses = [
            _tool_call(
                "parent-clarification-call",
                "ask_clarification",
                json.dumps(
                    {
                        "clarification_ref": "clarify_gabriele_identity",
                        "goal": "Store the memory with the correct person.",
                        "uncertainty": "The person is identified only as Gabriele.",
                        "relevant_context": "Two people named Gabriele are plausible.",
                        "relevant_refs": ["node_0001", "node_0002"],
                    }
                ),
            ),
            _tool_call(
                "child-question-call",
                "ask_user",
                json.dumps(
                    {
                        "clarification_ref": "clarify_gabriele_identity",
                        "question": "Which Gabriele do you mean?",
                        "mode": "single_choice",
                        "options": [
                            {
                                "label": "Gabriele Lucci",
                                "description": "The person at the barbecue.",
                            },
                            {
                                "label": "Another Gabriele",
                                "description": None,
                            },
                        ],
                    }
                ),
            ),
            ChatResponse(
                message=Msg(
                    role="assistant",
                    content={
                        "clarification_ref": "clarify_gabriele_identity",
                        "outcome": clarification_outcome,
                        "user_answer": (
                            "Gabriele Lucci" if clarification_outcome == "resolved" else None
                        ),
                        "resolved_point": (
                            "The mentioned person is Gabriele Lucci."
                            if clarification_outcome == "resolved"
                            else None
                        ),
                        "remaining_uncertainty": (
                            None
                            if clarification_outcome == "resolved"
                            else "The user did not answer before the deadline."
                        ),
                    },
                )
            ),
            ChatResponse(
                message=Msg(
                    role="assistant",
                    content=parent_message,
                )
            ),
        ]

    def make_client(self, _config: Any) -> object:
        return object()

    def describe(self, _config: Any) -> str:
        return "nested clarification scripted provider"

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(list(request.messages))
        return self.responses.pop(0)


@pytest.mark.parametrize(
    ("interaction_outcome", "clarification_outcome", "parent_message"),
    [
        (
            "answer",
            "resolved",
            "Thanks, I now know that you meant Gabriele Lucci.",
        ),
        (
            "timeout",
            "timed_out",
            "I could not resolve which Gabriele you meant because the question timed out.",
        ),
    ],
)
def test_answer_or_timeout_resumes_child_before_original_parent_tool_call(
    monkeypatch: Any,
    interaction_outcome: str,
    clarification_outcome: str,
    parent_message: str,
) -> None:
    provider = NestedClarificationProvider(
        clarification_outcome=clarification_outcome,
        parent_message=parent_message,
    )
    monkeypatch.setenv("BORIS_PROVIDER_DEFAULT", "openai")
    monkeypatch.setenv("BORIS_OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "product.ai.ai_clients.llm_core.llm_base.get_adapter",
        lambda *_args, **_kwargs: provider,
    )
    client = LLMInterfaceCore(
        logger=logging.getLogger("clarification-handoff-test"),
        base_path=Path.cwd(),
    )
    history_session = AgenticHistorySession()
    templates_root = Path(__file__).parents[1] / "src" / "product" / "prompts" / "templates"
    prompt_service = PromptService(FilePromptTemplateSource(templates_root), PromptRenderer())
    clarification_state = ClarificationState(
        client,
        history_session,
        prompt_service,
        build_ask_user_tool(
            UserInteractionService(response_timeout=timedelta(minutes=5))
        ),
    )
    continuation_store = InteractionContinuationStore()
    clarification_tool, clarification_handler = build_clarification_agent_tool(
        clarification_state,
        continuation_store,
    )
    parent_toolbox = ToolBox("parent", [clarification_tool])
    parent_state = BaseAgenticState("parent_state", client, history_session)

    paused_parent = parent_state.invoke(
        AgenticStateInvocationDTO(
            system_prompt="Ask for clarification when identity is materially ambiguous.",
            request="Remember that Gabriele attended the barbecue.",
            toolbox=parent_toolbox,
            parallel_tool_calls=False,
        )
    )

    assert paused_parent.outcome == "awaiting_input"
    assert paused_parent.continuation is not None
    clarification_handler.bind_parent_continuation(paused_parent.continuation)
    parent_call = paused_parent.continuation.tool_batch.calls[0]
    assert parent_call.provider_call_id == "parent-clarification-call"
    assert parent_call.interaction_request is not None
    packet = parent_call.interaction_request.interaction_packet
    assert packet.mode == QuestionMode.SINGLE_CHOICE
    assert packet.allow_other is True

    if interaction_outcome == "answer":
        parent_resume = clarification_handler.resolve_answer(
            UserQuestionAnswerDTO(
                interaction_ref=packet.interaction_ref,
                selected_option_refs=[packet.options[0].option_ref],
            )
        )
    else:
        parent_resume = clarification_handler.resolve_timeout(
            packet.interaction_ref,
            resolved_at=packet.deadline,
        )

    assert isinstance(parent_resume, ParentToolResumeDTO)
    with pytest.raises(ValueError, match="already been resolved"):
        if interaction_outcome == "answer":
            clarification_handler.resolve_answer(
                UserQuestionAnswerDTO(
                    interaction_ref=packet.interaction_ref,
                    selected_option_refs=[packet.options[0].option_ref],
                )
            )
        else:
            clarification_handler.resolve_timeout(
                packet.interaction_ref,
                resolved_at=packet.deadline,
            )
    assert parent_resume.tool_result.provider_call_id == "parent-clarification-call"
    completed_parent = parent_state.resume(
        AgenticStateResumeDTO(
            continuation=parent_resume.parent_continuation,
            tool_results=[parent_resume.tool_result],
            toolbox=parent_toolbox,
            parallel_tool_calls=False,
        )
    )

    assert completed_parent.outcome == "completed"
    assert completed_parent.assistant_message.as_text() == parent_message
    child_resume_tool = next(message for message in provider.requests[2] if message.role == "tool")
    assert child_resume_tool.meta["tool_call_id"] == "child-question-call"
    parent_resume_tool = next(message for message in provider.requests[3] if message.role == "tool")
    assert parent_resume_tool.meta["tool_call_id"] == "parent-clarification-call"
    parent_output = json.loads(str(parent_resume_tool.content))
    assert parent_output["status"] == "ok"
    assert parent_output["data"]["clarification_ref"] == "clarify_gabriele_identity"
    assert parent_output["data"]["outcome"] == clarification_outcome

