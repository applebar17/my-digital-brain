"""Functional clarification-state interaction and continuation behavior."""

import logging
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from product.agentic.contracts import ToolCallResultDTO
from product.agentic.history import AgenticHistorySession
from product.ai.ai_clients.llm_core.llm_core import LLMInterfaceCore
from product.ai.ai_clients.protocols.protocol_chat import ChatRequest, ChatResponse, Msg
from product.ai.ai_clients.protocols.protocol_tools import ToolOutputDTO
from product.application.interactions import QuestionMode, UserInteractionService
from product.application.states.clarification import (
    ClarificationRequestDTO,
    ClarificationResultDTO,
    ClarificationState,
)
from product.application.tools.user_interaction import build_ask_user_tool
from product.prompts import FilePromptTemplateSource, PromptRenderer, PromptService


class ClarificationScriptedProvider:
    """Return one question call followed by the interpreted structured result."""

    name = "clarification-scripted"

    def __init__(self) -> None:
        self.requests: list[list[Msg]] = []
        self.responses = [
            ChatResponse(
                message=Msg(role="assistant", content=None),
                tool_calls=[
                    SimpleNamespace(
                        id="provider-question-call",
                        function=SimpleNamespace(
                            name="ask_user",
                            arguments=(
                                '{"clarification_ref":"clarify_gabriele_identity",'
                                '"question":"Which Gabriele do you mean?",'
                                '"mode":"single_choice","options":['
                                '{"label":"Gabriele Lucci",'
                                '"description":"The person at the barbecue."},'
                                '{"label":"Another Gabriele","description":null}]}'
                            ),
                        ),
                    )
                ],
            ),
            ChatResponse(
                message=Msg(
                    role="assistant",
                    content={
                        "clarification_ref": "clarify_gabriele_identity",
                        "outcome": "resolved",
                        "user_answer": "Gabriele Lucci",
                        "resolved_point": "The mentioned person is Gabriele Lucci.",
                        "remaining_uncertainty": None,
                    },
                )
            ),
        ]

    def make_client(self, _config: Any) -> object:
        return object()

    def describe(self, _config: Any) -> str:
        return "clarification scripted provider"

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(list(request.messages))
        return self.responses.pop(0)


def test_clarification_pauses_for_user_then_returns_interpreted_result(
    monkeypatch: Any,
) -> None:
    provider = ClarificationScriptedProvider()
    monkeypatch.setenv("BORIS_PROVIDER_DEFAULT", "openai")
    monkeypatch.setenv("BORIS_OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "product.ai.ai_clients.llm_core.llm_base.get_adapter",
        lambda *_args, **_kwargs: provider,
    )
    client = LLMInterfaceCore(
        logger=logging.getLogger("clarification-state-test"),
        base_path=Path.cwd(),
    )
    templates_root = Path(__file__).parents[1] / "src" / "product" / "prompts" / "templates"
    prompt_service = PromptService(FilePromptTemplateSource(templates_root), PromptRenderer())
    state = ClarificationState(
        client,
        AgenticHistorySession(),
        prompt_service,
        build_ask_user_tool(
            UserInteractionService(response_timeout=timedelta(minutes=5))
        ),
    )

    paused = state.clarify(
        ClarificationRequestDTO(
            clarification_ref="clarify_gabriele_identity",
            goal="Resolve the person before storing the memory.",
            uncertainty="The memory identifies a person only as Gabriele.",
            relevant_context="Two plausible people are known in the supplied context.",
            relevant_refs=["node_0001", "node_0002"],
        )
    )

    assert paused.outcome == "awaiting_input"
    continuation = paused.continuation
    assert continuation is not None
    pending_call = continuation.tool_batch.calls[0]
    assert pending_call.provider_call_id == "provider-question-call"
    assert pending_call.interaction_request is not None
    packet = pending_call.interaction_request.interaction_packet
    assert packet.clarification_ref == "clarify_gabriele_identity"
    assert packet.mode == QuestionMode.SINGLE_CHOICE
    assert packet.interaction_ref
    assert len(packet.options) == 2
    assert packet.allow_other is True

    completed = state.resume_clarification(
        continuation,
        [
            ToolCallResultDTO(
                provider_call_id="provider-question-call",
                tool_output=ToolOutputDTO(
                    status="ok",
                    data={
                        "interaction_ref": packet.interaction_ref,
                        "clarification_ref": packet.clarification_ref,
                        "outcome": "answered",
                        "answer": "Gabriele Lucci",
                    },
                ),
            )
        ],
    )

    assert completed.outcome == "completed"
    assert isinstance(completed.structured_output, ClarificationResultDTO)
    assert completed.structured_output.clarification_ref == "clarify_gabriele_identity"
    assert completed.structured_output.resolved_point == "The mentioned person is Gabriele Lucci."
    resumed_tool_message = next(
        message for message in provider.requests[1] if message.role == "tool"
    )
    assert resumed_tool_message.meta["tool_call_id"] == "provider-question-call"

