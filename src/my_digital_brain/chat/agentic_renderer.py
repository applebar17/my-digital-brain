from __future__ import annotations

from typing import Any

from my_digital_brain.agentic.runtime_models import AgenticRunResult
from my_digital_brain.chat.enums import ChatDiagnosticLevel, ChatResponseStatus, PendingProcessKind
from my_digital_brain.chat.models import (
    ChatDiagnostic,
    ChatResponse,
    PendingProcessRef,
)


def render_agentic_chat_response(
    result: AgenticRunResult,
    *,
    session_id: str,
) -> ChatResponse:
    pending_process = _pending_process(result.pending_process_hints)
    failed = result.status in {"error", "max_transitions_exceeded"}
    status = (
        ChatResponseStatus.NEEDS_USER_INPUT
        if pending_process is not None
        else ChatResponseStatus.FAILED
        if failed
        else ChatResponseStatus.OK
    )
    primary_text = result.final_text or _fallback_text(status)
    return ChatResponse(
        session_id=session_id,
        status=status,
        primary_text=primary_text,
        pending_process=pending_process,
        diagnostics=_diagnostics(result),
        metadata={
            "operation": "agentic_runtime",
            "runtime_mode": "agentic",
            "agentic_status": result.status,
            "visited_states": [str(state) for state in result.visited_states],
            **_control_metadata(result),
        },
    )


def _pending_process(hints: list[dict[str, Any]]) -> PendingProcessRef | None:
    if not hints:
        return None
    hint = dict(hints[0])
    if "process_ref" in hint and isinstance(hint["process_ref"], dict):
        hint = {**hint["process_ref"], **{k: v for k, v in hint.items() if k != "process_ref"}}
    if not hint.get("process_id"):
        return None
    kind = hint.get("kind") or hint.get("process_kind") or PendingProcessKind.MEMORY_INGESTION
    return PendingProcessRef(
        process_id=str(hint["process_id"]),
        kind=kind,
        status=hint.get("status", "pending"),
        question=hint.get("question"),
        expires_at=hint.get("expires_at"),
        metadata=dict(hint.get("metadata") or {}),
    )


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
    metadata: dict[str, Any] = {}
    for state_result in result.state_results:
        for event in state_result.tool_events:
            data = event.data or {}
            result_payload = data.get("result")
            if isinstance(result_payload, dict):
                result_metadata = result_payload.get("metadata")
                if isinstance(result_metadata, dict) and result_metadata.get(
                    "clear_pending_process",
                ):
                    metadata["clear_pending_process"] = True
            if data.get("operation") == "cancel_pending_process":
                metadata["clear_pending_process"] = True
    return metadata


def _fallback_text(status: ChatResponseStatus) -> str:
    if status == ChatResponseStatus.NEEDS_USER_INPUT:
        return "I need one clarification before I can continue."
    if status == ChatResponseStatus.FAILED:
        return "I could not complete this request safely."
    return "Done."
