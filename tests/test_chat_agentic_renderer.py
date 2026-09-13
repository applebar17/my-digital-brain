from my_digital_brain.agentic.enums import AgenticStateId
from my_digital_brain.agentic.runtime_models import AgenticRunResult, AgenticStateRunResult
from my_digital_brain.chat.agentic_renderer import render_agentic_chat_response
from my_digital_brain.clarification.contracts import ClarificationPacket


def _packet() -> dict:
    return ClarificationPacket(
        frame_id="frame-1",
        tool_call_id="call-1",
        tool_name="ask_text",
        origin_state_id="clarification_agent",
        reason="Need one detail.",
        questions=[
            {
                "question": "What is the surname?",
                "kind": "missing_attribute",
                "response_mode": "free_text",
            }
        ],
    ).model_dump(mode="json")


def test_completed_result_does_not_republish_historical_clarification_packet() -> None:
    result = AgenticRunResult(
        status="ok",
        final_text="Done.",
        visited_states=[AgenticStateId.MEMORY_INGESTION],
        state_results=[
            AgenticStateRunResult(
                state_id=AgenticStateId.MEMORY_INGESTION,
                tool_events=[
                    {
                        "tool_name": "ask_clarification",
                        "status": "ok",
                        "data": {"clarification_packet": _packet()},
                    }
                ],
            )
        ],
    )

    response = render_agentic_chat_response(result, session_id="session-1")

    assert response.primary_text == "Done."
    assert response.clarification_packet is None
