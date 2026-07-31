from __future__ import annotations

from typing import Any

from my_digital_brain.core.ids import new_uuid

from .contracts import (
    ClarificationAnswer,
    ClarificationAnswerPacket,
    ClarificationHistoryMessage,
    ClarificationKind,
    ClarificationOption,
    ClarificationPacket,
    ClarificationQuestion,
    ClarificationResponseMode,
)


def build_clarification_packet(
    *,
    frame_id: str,
    origin_state_id: str,
    reason: str,
    questions: list[dict[str, Any]],
    tool_call_id: str | None = None,
    tool_name: str | None = None,
    target_refs: list[str] | None = None,
    history_delta: list[dict[str, Any]] | None = None,
    allowed_refs: set[str] | None = None,
) -> ClarificationPacket:
    packet = ClarificationPacket(
        frame_id=frame_id,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        origin_state_id=origin_state_id,
        reason=reason,
        questions=[
            ClarificationQuestion(
                question_id=str(question.get("question_id") or new_uuid()),
                question=str(question.get("question") or "").strip(),
                kind=ClarificationKind(
                    str(question.get("kind") or ClarificationKind.MISSING_ATTRIBUTE.value)
                ),
                response_mode=ClarificationResponseMode(
                    str(
                        question.get("response_mode")
                        or (
                            ClarificationResponseMode.SINGLE_CHOICE.value
                            if question.get("options")
                            and not bool(question.get("allow_custom_answer", True))
                            else (
                                ClarificationResponseMode.CHOICE_OR_TEXT.value
                                if question.get("options")
                                else ClarificationResponseMode.TEXT_OR_AUDIO.value
                            )
                        )
                    )
                ),
                options=[
                    ClarificationOption(
                        option_id=str(option.get("option_id") or new_uuid()),
                        target_ref=option.get("target_ref"),
                        label=str(option.get("label") or "").strip(),
                        summary=option.get("summary"),
                        recommended=bool(option.get("recommended", False)),
                    )
                    for option in question.get("options", [])
                    if str(option.get("label") or "").strip()
                ],
                target_refs=list(question.get("target_refs") or []),
                evidence_refs=list(question.get("evidence_refs") or []),
                allow_custom_answer=bool(question.get("allow_custom_answer", True)),
                required=bool(question.get("required", True)),
            )
            for question in questions
            if str(question.get("question") or "").strip()
        ],
        target_refs=target_refs or [],
        history_delta=[
            ClarificationHistoryMessage.model_validate(item) for item in (history_delta or [])
        ],
    )
    packet.validate_model_refs(allowed_refs)
    if not packet.history_delta:
        packet = packet.model_copy(
            update={
                "history_delta": [
                    ClarificationHistoryMessage(
                        role="assistant",
                        content=render_clarification_questions(packet),
                    )
                ]
            },
            deep=True,
        )
    return packet


def validate_clarification_answers(
    packet: ClarificationPacket,
    answers: ClarificationAnswerPacket,
) -> None:
    from my_digital_brain.chat.exceptions import ClarificationValidationError

    if answers.packet_id != packet.packet_id:
        raise ClarificationValidationError(
            "Clarification answer packet does not match the active packet.",
            code="clarification_packet_mismatch",
            packet_id=packet.packet_id,
            frame_id=packet.frame_id,
            details={"received_packet_id": answers.packet_id},
        )
    if answers.frame_id != packet.frame_id:
        raise ClarificationValidationError(
            "Clarification answer frame id does not match.",
            code="clarification_frame_mismatch",
            packet_id=packet.packet_id,
            frame_id=packet.frame_id,
            details={"received_frame_id": answers.frame_id},
        )
    if packet.tool_call_id and answers.tool_call_id != packet.tool_call_id:
        raise ClarificationValidationError(
            "Clarification answer tool call id does not match.",
            code="clarification_tool_call_mismatch",
            packet_id=packet.packet_id,
            frame_id=packet.frame_id,
            details={"received_tool_call_id": answers.tool_call_id},
        )

    questions = {question.question_id: question for question in packet.questions}
    for answer in answers.answers:
        question = questions.get(answer.question_id)
        if question is None:
            raise ClarificationValidationError(
                f"Unknown clarification question id: {answer.question_id}",
                code="clarification_question_unknown",
                packet_id=packet.packet_id,
                frame_id=packet.frame_id,
                question_ids=[answer.question_id],
            )
        allowed_options = {option.option_id for option in question.options}
        unknown_options = [
            option_id
            for option_id in answer.selected_option_ids
            if option_id not in allowed_options
        ]
        if unknown_options:
            raise ClarificationValidationError(
                "Clarification answer referenced unknown option ids: " + ", ".join(unknown_options),
                code="clarification_option_unknown",
                packet_id=packet.packet_id,
                frame_id=packet.frame_id,
                question_ids=[answer.question_id],
                details={"unknown_option_ids": unknown_options},
            )
        if (
            question.response_mode
            in {
                "single_choice",
                "confirmation",
                "choice_or_text",
            }
            and len(answer.selected_option_ids) > 1
        ):
            raise ClarificationValidationError(
                f"Question {answer.question_id} accepts only one selected option.",
                code="clarification_option_cardinality",
                packet_id=packet.packet_id,
                frame_id=packet.frame_id,
                question_ids=[answer.question_id],
            )
        has_text = bool((answer.text or "").strip())
        has_audio = bool((answer.audio_media_ref or "").strip())
        has_normalized_text = bool((answer.normalized_text or "").strip())
        has_option = bool(answer.selected_option_ids)
        if question.response_mode in {"free_text", "text_or_audio"} and has_option:
            raise ClarificationValidationError(
                f"Question {answer.question_id} does not accept choice options.",
                code="clarification_response_mode_mismatch",
                packet_id=packet.packet_id,
                frame_id=packet.frame_id,
                question_ids=[answer.question_id],
            )
        if (
            question.response_mode == "multiple_choice"
            and not has_option
            and not (has_text or has_audio)
        ):
            raise ClarificationValidationError(
                f"Question {answer.question_id} requires at least one selected option.",
                code="clarification_answer_required",
                packet_id=packet.packet_id,
                frame_id=packet.frame_id,
                question_ids=[answer.question_id],
            )
        if (
            question.required
            and not has_text
            and not has_audio
            and not has_normalized_text
            and not has_option
        ):
            raise ClarificationValidationError(
                f"Question {answer.question_id} requires an option, text, or audio answer.",
                code="clarification_answer_required",
                packet_id=packet.packet_id,
                frame_id=packet.frame_id,
                question_ids=[answer.question_id],
            )
        if (has_text or has_audio or has_normalized_text) and not question.allow_custom_answer:
            raise ClarificationValidationError(
                f"Question {answer.question_id} does not accept custom answers.",
                code="clarification_custom_answer_not_allowed",
                packet_id=packet.packet_id,
                frame_id=packet.frame_id,
                question_ids=[answer.question_id],
            )


def merge_clarification_progress(
    packet: ClarificationPacket,
    current_progress: dict[str, Any] | None,
    answers: ClarificationAnswerPacket,
) -> dict[str, Any]:
    progress = (
        dict(current_progress)
        if isinstance(current_progress, dict)
        and current_progress.get("packet_id") == packet.packet_id
        else {}
    )
    answers_by_question_id = dict(progress.get("answers_by_question_id") or {})
    for answer in answers.answers:
        answers_by_question_id[answer.question_id] = answer.model_dump(
            mode="json",
            exclude_none=True,
        )
    question_ids = [question.question_id for question in packet.questions]
    answered_question_ids = [
        question_id for question_id in question_ids if question_id in answers_by_question_id
    ]
    current_question_id = next(
        (question_id for question_id in question_ids if question_id not in answers_by_question_id),
        None,
    )
    return {
        "packet_id": packet.packet_id,
        "answered_question_ids": answered_question_ids,
        "current_question_id": current_question_id,
        "is_complete": len(answered_question_ids) == len(question_ids),
        "answers_by_question_id": answers_by_question_id,
    }


def answer_packet_from_progress(
    packet: ClarificationPacket,
    progress: dict[str, Any],
) -> ClarificationAnswerPacket:
    from my_digital_brain.chat.exceptions import ChatValidationError

    answers_by_question_id = progress.get("answers_by_question_id")
    if not isinstance(answers_by_question_id, dict):
        raise ChatValidationError("Clarification progress does not contain answers.")
    answers = []
    for question in packet.questions:
        answer_payload = answers_by_question_id.get(question.question_id)
        if not isinstance(answer_payload, dict):
            raise ChatValidationError(
                f"Clarification question is missing an answer: {question.question_id}",
            )
        answers.append(ClarificationAnswer.model_validate(answer_payload))
    return ClarificationAnswerPacket(
        packet_id=packet.packet_id,
        frame_id=packet.frame_id,
        tool_call_id=packet.tool_call_id or "",
        answers=answers,
    )


def resolved_clarifications_from_answers(
    packet: ClarificationPacket,
    answers: ClarificationAnswerPacket,
) -> list[dict[str, Any]]:
    question_by_id = {question.question_id: question for question in packet.questions}
    resolved: list[dict[str, Any]] = []
    for answer in answers.answers:
        question = question_by_id.get(answer.question_id)
        if question is None:
            continue
        selected = [
            {
                "option_id": option.option_id,
                "target_ref": option.target_ref,
                "label": option.label,
                "recommended": option.recommended,
            }
            for option in question.options
            if option.option_id in answer.selected_option_ids
        ]
        text = (answer.text or "").strip()
        normalized_text = (answer.normalized_text or "").strip()
        answer_text = normalized_text or text or ", ".join(option["label"] for option in selected)
        resolved.append(
            {
                "question_id": question.question_id,
                "question": question.question,
                "answer": answer_text,
                "selected_options": selected,
                "text": text or None,
                "normalized_text": normalized_text or None,
                "audio_media_ref": answer.audio_media_ref,
                "source": "user",
                "authoritative": True,
            }
        )
    return resolved


def summarize_clarification_answers(
    packet: ClarificationPacket,
    answers: ClarificationAnswerPacket,
) -> str:
    question_by_id = {question.question_id: question for question in packet.questions}
    lines = ["Clarification answers:"]
    for answer in answers.answers:
        question = question_by_id[answer.question_id]
        labels = _selected_labels(question, answer.selected_option_ids)
        parts = []
        if labels:
            parts.append("selected " + ", ".join(labels))
        text = (answer.normalized_text or answer.text or "").strip()
        if text:
            parts.append(f'custom answer "{text}"')
        if answer.audio_media_ref:
            parts.append("audio answer")
        rendered = "; ".join(parts) if parts else "no answer"
        lines.append(f"- {question.question}: {rendered}")
    return "\n".join(lines)


def render_clarification_questions(packet: ClarificationPacket) -> str:
    lines = ["Clarification needed:"]
    for index, question in enumerate(packet.questions, start=1):
        lines.append(f"{index}. {question.question}")
        if question.options:
            option_labels = ", ".join(
                f"{option.label} ({option.summary})" if option.summary else option.label
                for option in question.options
            )
            lines.append(f"   Options: {option_labels}")
        if question.allow_custom_answer:
            lines.append("   Other: custom text or audio is allowed.")
    return "\n".join(lines)


def _selected_labels(question: ClarificationQuestion, option_ids: list[str]) -> list[str]:
    by_id = {option.option_id: option.label for option in question.options}
    return [by_id[option_id] for option_id in option_ids if option_id in by_id]
