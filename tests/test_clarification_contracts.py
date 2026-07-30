from __future__ import annotations

import pytest
from pydantic import ValidationError

from my_digital_brain.clarification.contracts import (
    ClarificationAnswer,
    ClarificationAnswerPacket,
    ClarificationDoubt,
    ClarificationHandoffRequest,
    ClarificationKind,
    ClarificationOption,
    ClarificationPacket,
    ClarificationQuestion,
    ClarificationResolutionReport,
    ClarificationResponseMode,
    clarification_doubts_schema,
)
from my_digital_brain.clarification.interaction import validate_clarification_answers


def _doubt(**overrides: object) -> dict[str, object]:
    return {
        "doubt_id": "DOUBT_001",
        "doubt": "Amos has no identifying surname.",
        "refs": ["CANDIDATE_PERSON_001"],
        "missing_information": "Full name",
        "why_blocking": "The identity is ambiguous.",
        "evidence_refs": ["CANDIDATE_EVENT_001"],
        **overrides,
    }


def test_handoff_requires_detailed_doubts() -> None:
    request = ClarificationHandoffRequest(
        doubts=[_doubt()],
        invoker_state_id="node",
        invoker_tool_call_id="call-1",
    )

    assert request.doubts[0].refs == ["CANDIDATE_PERSON_001"]
    assert request.invoker_tool_call_id == "call-1"


def test_empty_handoff_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClarificationHandoffRequest(doubts=[], invoker_state_id="node")


def test_resolution_report_accepts_informational_statuses() -> None:
    for status in ("resolved", "partially_resolved", "unresolved", "user_declined", "not_needed"):
        report = ClarificationResolutionReport(
            entries=[{"doubt_id": "DOUBT_001", "status": status}],
        )
        assert report.entries[0].status == status


def test_resolution_report_requires_one_entry_per_handoff_doubt() -> None:
    handoff = ClarificationHandoffRequest(
        doubts=[_doubt(), _doubt(doubt_id="DOUBT_002")],
        invoker_state_id="node",
    )
    report = ClarificationResolutionReport(
        entries=[{"doubt_id": "DOUBT_001", "status": "resolved"}],
    )

    with pytest.raises(ValueError, match="exactly one entry per doubt"):
        report.validate_against(handoff)


def test_tool_schema_requires_doubt_fields_and_no_question_fields() -> None:
    schema = clarification_doubts_schema()
    item = schema["items"]

    assert "doubt" in item["required"]
    assert "evidence_refs" in item["required"]
    assert "question" not in item["properties"]
    assert "options" not in item["properties"]


def test_doubt_contract_preserves_model_facing_refs_without_graph_ids() -> None:
    doubt = ClarificationDoubt.model_validate(_doubt())

    assert doubt.refs == ["CANDIDATE_PERSON_001"]
    assert "person:owner" not in doubt.model_dump_json()


def test_all_clarification_kinds_and_response_modes_are_contract_values() -> None:
    assert {item.value for item in ClarificationKind} == {
        "identity_no_match",
        "identity_ambiguous",
        "missing_attribute",
        "confirm_proposal",
        "correct_conflict",
        "relationship_target",
        "explicit_discard",
    }
    assert {item.value for item in ClarificationResponseMode} == {
        "free_text",
        "single_choice",
        "multiple_choice",
        "confirmation",
        "choice_or_text",
        "text_or_audio",
    }


def test_packet_supports_five_parallel_questions_with_unique_associations() -> None:
    questions = [
        ClarificationQuestion(
            question_id=f"QUESTION_{index}",
            question=f"Question {index}?",
            kind=ClarificationKind.MISSING_ATTRIBUTE,
            response_mode=ClarificationResponseMode.TEXT_OR_AUDIO,
            target_refs=[f"CANDIDATE_PERSON_{index:03d}"],
        )
        for index in range(1, 6)
    ]
    packet = ClarificationPacket(
        frame_id="frame-1",
        origin_state_id="node",
        reason="Several independent values are missing.",
        questions=questions,
    )

    assert len(packet.questions) == 5
    assert packet.questions[0].allow_custom_answer is True


def test_packet_rejects_a_sixth_question_and_duplicate_ids() -> None:
    question = ClarificationQuestion(
        question="Who is Amos?",
        kind=ClarificationKind.IDENTITY_NO_MATCH,
        response_mode=ClarificationResponseMode.TEXT_OR_AUDIO,
    )
    with pytest.raises(ValidationError):
        ClarificationPacket(
            frame_id="frame-1",
            origin_state_id="node",
            reason="Too many questions.",
            questions=[
                question.model_copy(update={"question_id": str(index)}) for index in range(6)
            ],
        )
    with pytest.raises(ValidationError, match="question IDs must be unique"):
        ClarificationPacket(
            frame_id="frame-1",
            origin_state_id="node",
            reason="Duplicate question.",
            questions=[question, question.model_copy(deep=True)],
        )


def test_question_modes_validate_options_and_confirmation_shape() -> None:
    with pytest.raises(ValidationError):
        ClarificationQuestion(
            question="What should I remember?",
            kind=ClarificationKind.MISSING_ATTRIBUTE,
            response_mode=ClarificationResponseMode.FREE_TEXT,
            options=[ClarificationOption(label="A")],
        )
    with pytest.raises(ValidationError):
        ClarificationQuestion(
            question="Is this correct?",
            kind=ClarificationKind.CONFIRM_PROPOSAL,
            response_mode=ClarificationResponseMode.CONFIRMATION,
            options=[ClarificationOption(label="Yes")],
        )
    question = ClarificationQuestion(
        question="Is this correct?",
        kind=ClarificationKind.CONFIRM_PROPOSAL,
        response_mode=ClarificationResponseMode.CONFIRMATION,
        options=[ClarificationOption(label="Yes"), ClarificationOption(label="No")],
        allow_custom_answer=False,
    )
    assert question.allow_custom_answer is False


def test_answers_support_text_audio_and_custom_correction() -> None:
    packet = ClarificationPacket(
        frame_id="frame-1",
        origin_state_id="node",
        reason="Resolve an ambiguous identity.",
        questions=[
            ClarificationQuestion(
                question_id="question-1",
                question="Which Amos is this?",
                kind=ClarificationKind.IDENTITY_AMBIGUOUS,
                response_mode=ClarificationResponseMode.CHOICE_OR_TEXT,
                options=[
                    ClarificationOption(
                        option_id="option-1",
                        label="Amos Bianchi",
                        summary="Friend from elementary school",
                    )
                ],
            )
        ],
    )
    answers = ClarificationAnswerPacket(
        packet_id=packet.packet_id,
        frame_id=packet.frame_id,
        tool_call_id="call-1",
        answers=[
            ClarificationAnswer(
                question_id="question-1",
                audio_media_ref="telegram:file:audio-1",
                normalized_text="Amos Vignaroli",
            )
        ],
    )

    validate_clarification_answers(packet, answers)
    assert answers.answers[0].normalized_text == "Amos Vignaroli"


def test_normalized_text_is_a_valid_backend_answer_without_raw_input() -> None:
    packet = ClarificationPacket(
        frame_id="frame-1",
        origin_state_id="node",
        reason="Normalize an answer.",
        questions=[
            ClarificationQuestion(
                question="Who is Amos?",
                kind=ClarificationKind.IDENTITY_NO_MATCH,
                response_mode=ClarificationResponseMode.TEXT_OR_AUDIO,
            )
        ],
    )
    answers = ClarificationAnswerPacket(
        packet_id=packet.packet_id,
        frame_id=packet.frame_id,
        tool_call_id="call-1",
        answers=[
            ClarificationAnswer(
                question_id=packet.questions[0].question_id,
                normalized_text="Amos Vignaroli",
            )
        ],
    )

    validate_clarification_answers(packet, answers)


def test_packet_refs_reject_graph_ids_and_unknown_context_refs() -> None:
    packet = ClarificationPacket(
        frame_id="frame-1",
        origin_state_id="node",
        reason="Resolve an identity.",
        target_refs=["CANDIDATE_PERSON_001"],
        questions=[
            ClarificationQuestion(
                question="Who is Amos?",
                kind=ClarificationKind.IDENTITY_NO_MATCH,
                response_mode=ClarificationResponseMode.TEXT_OR_AUDIO,
            )
        ],
    )
    packet.validate_model_refs({"CANDIDATE_PERSON_001"})
    with pytest.raises(ValueError, match="not supplied"):
        packet.validate_model_refs({"CANDIDATE_PERSON_002"})
    with pytest.raises(ValueError, match="persisted graph IDs"):
        packet.model_copy(update={"target_refs": ["person:owner"]}).validate_model_refs()


def test_other_is_a_custom_answer_without_a_target_ref() -> None:
    option = ClarificationOption(option_id="option-1", label="Amos Bianchi")
    assert option.target_ref is None
