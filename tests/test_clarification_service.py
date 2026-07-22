from my_digital_brain.agentic import AgenticHistoryService
from my_digital_brain.chat.models import ClarificationPacket
from my_digital_brain.clarification import ClarificationService


def test_ask_clarification_returns_one_transport_neutral_packet() -> None:
    service = ClarificationService()

    result = service.ask(
        reason="Two supplied people match the name.",
        questions=[
            {
                "question": "Which Marco did you mean?",
                "options": [{"label": "Marco Bianchi"}, {"label": "Marco Rossi"}],
            }
        ],
        target_refs=["CANDIDATE_PERSON_001"],
    )

    assert result.status == "pending"
    packet = ClarificationPacket.model_validate(result.data["clarification_packet"])
    assert packet.questions[0].question == "Which Marco did you mean?"
    assert packet.target_refs == ["CANDIDATE_PERSON_001"]
    assert result.data["operation"] == "ask_clarification"


def test_answer_text_appends_user_history_without_pipeline_status() -> None:
    service = ClarificationService()
    result = service.ask(
        reason="The place is ambiguous.",
        questions=[{"question": "Which place was it?"}],
    )
    packet = ClarificationPacket.model_validate(result.data["clarification_packet"])

    _, answer_history = service.answer_text(packet, "The beach club in Rimini")
    history = AgenticHistoryService().promote_messages_to_master_history(
        [],
        [*packet.history_delta, *answer_history],
    )

    assert [item["role"] for item in history] == ["assistant", "user"]
    assert history[-1]["content"] == "Clarification answer: The beach club in Rimini"
