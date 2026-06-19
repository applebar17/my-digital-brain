from __future__ import annotations

from typing import Any

from my_digital_brain.chat.exceptions import ChatValidationError
from my_digital_brain.chat.models import (
    ClarificationAnswerPacket,
    ClarificationHistoryMessage,
    ClarificationOption,
    ClarificationPacket,
    ClarificationQuestion,
)
from my_digital_brain.chat.enums import ConversationMessageRole
from my_digital_brain.core.ids import new_uuid


def build_clarification_packet(
    *,
    process_id: str,
    origin_state_id: str,
    reason: str,
    questions: list[dict[str, Any]],
    compact_summary: str | None = None,
    target_refs: list[str] | None = None,
    history_delta: list[dict[str, Any]] | None = None,
) -> ClarificationPacket:
    packet = ClarificationPacket(
        process_id=process_id,
        origin_state_id=origin_state_id,
        reason=reason,
        questions=[
            ClarificationQuestion(
                question_id=str(question.get("question_id") or new_uuid()),
                question=str(question.get("question") or "").strip(),
                options=[
                    ClarificationOption(
                        option_id=str(option.get("option_id") or new_uuid()),
                        label=str(option.get("label") or "").strip(),
                        description=option.get("description"),
                        recommended=bool(option.get("recommended", False)),
                    )
                    for option in question.get("options", [])
                    if str(option.get("label") or "").strip()
                ][:5],
                free_text_allowed=bool(question.get("free_text_allowed", True)),
                required=bool(question.get("required", True)),
                selection_mode=str(question.get("selection_mode") or "single"),
            )
            for question in questions[:3]
            if str(question.get("question") or "").strip()
        ],
        compact_summary=compact_summary,
        target_refs=target_refs or [],
        history_delta=[
            ClarificationHistoryMessage.model_validate(item)
            for item in (history_delta or [])
        ],
    )
    if not packet.history_delta:
        packet = packet.model_copy(
            update={
                "history_delta": [
                    ClarificationHistoryMessage(
                        role=ConversationMessageRole.ASSISTANT,
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
    if answers.packet_id != packet.packet_id:
        raise ChatValidationError("Clarification answer packet does not match the active packet.")
    if answers.process_id != packet.process_id:
        raise ChatValidationError("Clarification answer process id does not match.")

    questions = {question.question_id: question for question in packet.questions}
    for answer in answers.answers:
        question = questions.get(answer.question_id)
        if question is None:
            raise ChatValidationError(
                f"Unknown clarification question id: {answer.question_id}",
            )
        allowed_options = {option.option_id for option in question.options}
        unknown_options = [
            option_id
            for option_id in answer.selected_option_ids
            if option_id not in allowed_options
        ]
        if unknown_options:
            raise ChatValidationError(
                "Clarification answer referenced unknown option ids: "
                + ", ".join(unknown_options),
            )
        if question.selection_mode == "single" and len(answer.selected_option_ids) > 1:
            raise ChatValidationError(
                f"Question {answer.question_id} accepts only one selected option.",
            )
        has_free_text = bool((answer.free_text or "").strip())
        has_option = bool(answer.selected_option_ids)
        if question.required and not has_free_text and not has_option:
            raise ChatValidationError(
                f"Question {answer.question_id} requires an option or free-text answer.",
            )
        if has_free_text and not question.free_text_allowed:
            raise ChatValidationError(
                f"Question {answer.question_id} does not accept free-text answers.",
            )


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
        free_text = (answer.free_text or "").strip()
        if free_text:
            parts.append(f'free text "{free_text}"')
        rendered = "; ".join(parts) if parts else "no answer"
        lines.append(f"- {question.question}: {rendered}")
    return "\n".join(lines)


def render_clarification_questions(packet: ClarificationPacket) -> str:
    lines = ["Clarification needed:"]
    if packet.compact_summary:
        lines.append(packet.compact_summary)
    for index, question in enumerate(packet.questions, start=1):
        lines.append(f"{index}. {question.question}")
        if question.options:
            option_labels = ", ".join(option.label for option in question.options)
            lines.append(f"   Options: {option_labels}")
        if question.free_text_allowed:
            lines.append("   Free text is allowed.")
    return "\n".join(lines)


def _selected_labels(question: ClarificationQuestion, option_ids: list[str]) -> list[str]:
    by_id = {option.option_id: option.label for option in question.options}
    return [by_id[option_id] for option_id in option_ids if option_id in by_id]
