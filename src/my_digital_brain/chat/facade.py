from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field

from my_digital_brain.chat.enums import ChatDiagnosticLevel, ChatResponseStatus
from my_digital_brain.chat.models import (
    ChatAction,
    ChatDiagnostic,
    ChatEvidenceRef,
    ChatModel,
    ClarificationPacket,
    PendingProcessContext,
    PendingProcessRef,
)


class ChatToolRequest(ChatModel):
    session_id: str
    channel: str
    conversation_id: str
    owner_id: str
    text: str
    pending_process_context: PendingProcessContext | None = None
    conversation_history_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatToolResult(ChatModel):
    status: ChatResponseStatus = ChatResponseStatus.OK
    primary_text: str
    pending_process: PendingProcessRef | None = None
    clarification_packet: ClarificationPacket | None = None
    actions: list[ChatAction] = Field(default_factory=list)
    evidence: list[ChatEvidenceRef] = Field(default_factory=list)
    diagnostics: list[ChatDiagnostic] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CancelPendingProcessRequest(ChatModel):
    session_id: str
    pending_process_id: str | None = None
    owner_id: str
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BackendToolFacade(Protocol):
    def start_memory_ingestion(self, request: ChatToolRequest) -> ChatToolResult: ...

    def query_memory_context(self, request: ChatToolRequest) -> ChatToolResult: ...

    def propose_memory_correction(self, request: ChatToolRequest) -> ChatToolResult: ...

    def get_conversation_status(self, request: ChatToolRequest) -> ChatToolResult: ...

    def resume_pending_process(self, request: ChatToolRequest) -> ChatToolResult: ...

    def pause_pending_process(self, request: CancelPendingProcessRequest) -> ChatToolResult: ...

    def cancel_pending_process(self, request: CancelPendingProcessRequest) -> ChatToolResult: ...


class NoopBackendToolFacade:
    """Safe placeholder facade for chat runtime wiring.

    Real ingestion/query/correction behavior is injected behind the same protocol
    as later waves connect the chat runtime to business services.
    """

    def start_memory_ingestion(self, request: ChatToolRequest) -> ChatToolResult:
        return _missing_backend_service_result(
            "start_memory_ingestion",
            "Memory ingestion is not configured, so I could not store this memory.",
            "Configure an IngestionService behind MemoryBackendToolFacade before exposing "
            "start_memory_ingestion.",
        )

    def query_memory_context(self, request: ChatToolRequest) -> ChatToolResult:
        return _missing_backend_service_result(
            "query_memory_context",
            "Memory query is not configured, so I could not search your graph.",
            "Configure GraphService and a graph answer path behind MemoryBackendToolFacade.",
        )

    def propose_memory_correction(self, request: ChatToolRequest) -> ChatToolResult:
        return _missing_backend_service_result(
            "propose_memory_correction",
            "Memory correction is not configured, so I could not prepare a safe update.",
            "Configure GraphService-backed correction tooling behind MemoryBackendToolFacade.",
        )

    def get_conversation_status(self, request: ChatToolRequest) -> ChatToolResult:
        if request.pending_process_context is None:
            return ChatToolResult(
                status=ChatResponseStatus.OK,
                primary_text="There is no pending process for this conversation.",
                metadata={"operation": "get_conversation_status"},
            )
        return ChatToolResult(
            status=ChatResponseStatus.OK,
            primary_text="There is a pending process for this conversation.",
            pending_process=request.pending_process_context.process_ref,
            metadata={"operation": "get_conversation_status"},
        )

    def resume_pending_process(self, request: ChatToolRequest) -> ChatToolResult:
        if request.pending_process_context is None:
            return ChatToolResult(
                status=ChatResponseStatus.FAILED,
                primary_text="There is no pending process to resume.",
                metadata={"operation": "resume_pending_process"},
            )
        return _missing_backend_service_result(
            "resume_pending_process",
            "Pending process resume is not configured, so I could not continue this memory.",
            "Configure an IngestionService before exposing resume_pending_process.",
            metadata={
                "pending_process_id": request.pending_process_context.process_ref.process_id,
            },
        )

    def pause_pending_process(self, request: CancelPendingProcessRequest) -> ChatToolResult:
        if request.pending_process_id is None:
            return ChatToolResult(
                status=ChatResponseStatus.OK,
                primary_text="There is no pending process to pause.",
                metadata={"operation": "pause_pending_process"},
            )
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="I paused the pending process and can come back to it later.",
            metadata={
                "operation": "pause_pending_process",
                "clear_pending_process": True,
                "pending_process_id": request.pending_process_id,
            },
        )

    def cancel_pending_process(self, request: CancelPendingProcessRequest) -> ChatToolResult:
        if request.pending_process_id is None:
            return ChatToolResult(
                status=ChatResponseStatus.OK,
                primary_text="There is no pending process to cancel.",
                metadata={"operation": "cancel_pending_process", "clear_pending_process": True},
            )
        return ChatToolResult(
            status=ChatResponseStatus.CANCELLED,
            primary_text="I cancelled the pending process.",
            metadata={
                "operation": "cancel_pending_process",
                "clear_pending_process": True,
                "pending_process_id": request.pending_process_id,
            },
        )


def _missing_backend_service_result(
    operation: str,
    primary_text: str,
    hint: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> ChatToolResult:
    return ChatToolResult(
        status=ChatResponseStatus.FAILED,
        primary_text=primary_text,
        diagnostics=[
            ChatDiagnostic(
                level=ChatDiagnosticLevel.ERROR,
                code="missing_backend_service",
                message=hint,
                details={"operation": operation},
            ),
        ],
        metadata={"operation": operation, **(metadata or {})},
    )
