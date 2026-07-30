from __future__ import annotations

from typing import Any

from my_digital_brain.agentic.runtime_models import AgenticRunResult
from my_digital_brain.chat.enums import ChatDiagnosticLevel, ChatResponseStatus
from my_digital_brain.chat.models import (
    ChatDiagnostic,
    ChatResponse,
)
from my_digital_brain.clarification.contracts import ClarificationPacket


def render_agentic_chat_response(
    result: AgenticRunResult,
    *,
    session_id: str,
) -> ChatResponse:
    failed = result.status in {"error", "max_transitions_exceeded"}
    status = (
        ChatResponseStatus.AWAITING_CLARIFICATION
        if result.interruption is not None
        else ChatResponseStatus.FAILED
        if failed
        else ChatResponseStatus.OK
    )
    primary_text = result.final_text or _fallback_text(status)
    clarification_packet = _clarification_packet(result)
    return ChatResponse(
        session_id=session_id,
        status=status,
        primary_text=primary_text,
        clarification_packet=clarification_packet,
        diagnostics=_diagnostics(result),
        metadata={
            "operation": "agentic_runtime",
            "runtime_mode": "agentic",
            "agentic_status": result.status,
            "visited_states": [str(state) for state in result.visited_states],
            **_control_metadata(result),
        },
    )


def _clarification_packet(
    result: AgenticRunResult,
) -> ClarificationPacket | None:
    if result.interruption is not None:
        packet = result.interruption.get("clarification_packet")
        if isinstance(packet, dict):
            return ClarificationPacket.model_validate(packet)
    for state_result in result.state_results:
        for event in state_result.tool_events:
            data = event.data or {}
            packet = data.get("clarification_packet")
            if isinstance(packet, dict):
                return ClarificationPacket.model_validate(packet)
    return None


def _diagnostics(result: AgenticRunResult) -> list[ChatDiagnostic]:
    diagnostics: list[ChatDiagnostic] = []
    for state_result in result.state_results:
        for event in state_result.tool_events:
            if event.status == "ok" or not event.error:
                continue
            diagnostics.append(
                ChatDiagnostic(
                    level=ChatDiagnosticLevel.ERROR,
                    code=str(event.error.get("code") or "agentic_tool_error"),
                    message=str(event.error.get("message") or "Agentic tool failed."),
                    details={
                        "state_id": str(state_result.state_id),
                        "tool_name": event.tool_name,
                    },
                )
            )
    return diagnostics


def _control_metadata(result: AgenticRunResult) -> dict[str, Any]:
    if result.interruption is None:
        return {}
    return {
        "active_agentic_frame_id": result.interruption.get("frame_id"),
        "active_tool_call_id": result.interruption.get("tool_call_id"),
        "active_tool_name": result.interruption.get("tool_name"),
    }


def _fallback_text(status: ChatResponseStatus) -> str:
    if status == ChatResponseStatus.AWAITING_CLARIFICATION:
        return "I need one clarification before I can continue."
    if status == ChatResponseStatus.FAILED:
        return "I could not complete this request safely."
    return "Done."
