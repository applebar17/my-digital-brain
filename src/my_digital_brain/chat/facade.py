from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field

from my_digital_brain.chat.enums import ChatResponseStatus
from my_digital_brain.chat.models import (
    ChatAction,
    ChatDiagnostic,
    ChatEvidenceRef,
    ChatModel,
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

    def cancel_pending_process(self, request: CancelPendingProcessRequest) -> ChatToolResult: ...


class NoopBackendToolFacade:
    """Safe placeholder facade for chat runtime wiring.

    Real ingestion/query/correction behavior is injected behind the same protocol
    as later waves connect the chat runtime to business services.
    """

    def start_memory_ingestion(self, request: ChatToolRequest) -> ChatToolResult:
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="I received this memory for processing.",
            metadata={"operation": "start_memory_ingestion", "wave": "chat_wave_1"},
        )

    def query_memory_context(self, request: ChatToolRequest) -> ChatToolResult:
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="I received your memory question. Query answering is not wired yet.",
            metadata={"operation": "query_memory_context", "wave": "chat_wave_1"},
        )

    def propose_memory_correction(self, request: ChatToolRequest) -> ChatToolResult:
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="I received this correction for review.",
            metadata={"operation": "propose_memory_correction", "wave": "chat_wave_1"},
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
