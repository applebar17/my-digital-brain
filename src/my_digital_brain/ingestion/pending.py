"""Conversion of provider and agentic pauses into ingestion results."""

from __future__ import annotations

from typing import Any

from my_digital_brain.ai.session import LLMSessionAwaitingTool
from my_digital_brain.agentic.runtime_models import AgenticStateRunResult
from my_digital_brain.ingestion.contracts import IngestionPendingInteraction


def pending_from_session(
    result: LLMSessionAwaitingTool,
    *,
    stage: str,
) -> IngestionPendingInteraction:
    pending_calls = result.continuation.pending_tool_calls
    pending_call = pending_calls[0]
    packet = result.continuation.pending_interaction.get("clarification_packet")
    if not isinstance(packet, dict):
        packet = _clarification_packet(result.tool_events, pending_call.call_id)
    return IngestionPendingInteraction(
        stage=stage,
        session_id=result.session_id,
        tool_call_id=pending_call.call_id,
        tool_name=pending_call.name,
        messages=result.messages,
        clarification_packet=packet,
        continuation=result.continuation,
        metadata={
            "source": "llm_session",
            "tool_call_ids": [call.call_id for call in pending_calls],
            "pending_interaction": result.continuation.pending_interaction,
        },
    )


def pending_from_agentic(
    result: AgenticStateRunResult,
    *,
    stage: str,
) -> IngestionPendingInteraction | None:
    if result.status != "interrupted":
        return None
    interruption = result.metadata.get("interruption") or {}
    packet = interruption.get("clarification_packet")
    messages = [
        message for message in interruption.get("messages") or [] if isinstance(message, dict)
    ]
    return IngestionPendingInteraction(
        stage=stage,
        session_id=str(interruption.get("frame_id") or "") or None,
        tool_call_id=str(interruption.get("tool_call_id") or "") or None,
        tool_name=str(interruption.get("tool_name") or "") or None,
        messages=messages,
        clarification_packet=packet if isinstance(packet, dict) else None,
        metadata={"source": "agentic_state", **interruption},
    )


def _clarification_packet(events: list[Any], call_id: str) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.call_id != call_id:
            continue
        data = event.result.data
        if isinstance(data, dict) and isinstance(data.get("clarification_packet"), dict):
            return data["clarification_packet"]
    return None
