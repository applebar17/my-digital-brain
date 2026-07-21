from __future__ import annotations

from typing import Any

from my_digital_brain.ai.models import ToolResult
from my_digital_brain.core.ids import new_uuid


class ClarificationService:
    """Single transport-neutral boundary for agent clarification requests."""

    def ask(
        self,
        *,
        reason: str,
        questions: list[dict[str, Any]],
        frame_id: str | None = None,
        state_id: str = "unknown",
        target_refs: list[str] | None = None,
    ) -> ToolResult:
        from my_digital_brain.chat.clarification import (
            build_clarification_packet,
            render_clarification_questions,
        )

        packet = build_clarification_packet(
            frame_id=frame_id or new_uuid(),
            origin_state_id=state_id,
            reason=reason,
            questions=questions,
            target_refs=target_refs or [],
        )
        return ToolResult(
            status="pending",
            output=render_clarification_questions(packet),
            data={
                "operation": "ask_clarification",
                "frame_id": packet.frame_id,
                "clarification_packet": packet.model_dump(
                    mode="json",
                    exclude_none=True,
                ),
                "history_delta": [
                    message.model_dump(mode="json", exclude_none=True)
                    for message in packet.history_delta
                ],
            },
        )

    def answer_text(
        self,
        packet: Any,
        answer_text: str,
    ) -> tuple[Any, list[dict[str, str]]]:
        from my_digital_brain.chat.clarification import validate_clarification_answers
        from my_digital_brain.chat.enums import ConversationMessageRole
        from my_digital_brain.chat.models import (
            ClarificationAnswer,
            ClarificationAnswerPacket,
        )

        answer_text = answer_text.strip()
        if not answer_text:
            raise ValueError("Clarification answer cannot be empty.")
        question = packet.questions[0]
        answers = ClarificationAnswer(
            question_id=question.question_id,
            free_text=answer_text,
        )
        answer_packet = ClarificationAnswerPacket(
            packet_id=packet.packet_id,
            frame_id=packet.frame_id,
            tool_call_id=packet.tool_call_id or "",
            answers=[answers],
        )
        validate_clarification_answers(packet, answer_packet)
        return answer_packet, [
            {
                "role": ConversationMessageRole.USER.value,
                "content": f"Clarification answer: {answer_text}",
            }
        ]

    def append_history(
        self,
        history: list[dict[str, Any]],
        packet: Any,
        answer_history: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        return [
            *history,
            *[
                message.model_dump(mode="json", exclude_none=True)
                for message in packet.history_delta
            ],
            *answer_history,
        ]
