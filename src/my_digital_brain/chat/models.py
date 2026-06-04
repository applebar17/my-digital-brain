from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from my_digital_brain.chat.enums import (
    ChatChannel,
    ChatDiagnosticLevel,
    ChatResponseStatus,
    ConversationMessageRole,
    ConversationStatus,
    PendingProcessKind,
    PendingProcessStatus,
)
from my_digital_brain.core.ids import new_uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChatModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        use_enum_values=True,
    )


class IncomingMediaRef(ChatModel):
    media_id: str = Field(default_factory=new_uuid)
    media_type: str = Field(description="Channel-neutral media kind such as voice, audio, image.")
    storage_ref: str | None = Field(
        default=None,
        description="Internal storage reference if the media has already been stored.",
    )
    mime_type: str | None = None
    file_name: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncomingChatMessage(ChatModel):
    channel: ChatChannel
    session_id: str | None = Field(
        default=None,
        description="Internal chat session id when the client is continuing an existing chat.",
    )
    conversation_id: str = Field(description="Channel conversation id before internal mapping.")
    sender_id: str
    owner_id: str
    message_id: str = Field(description="Channel message id.")
    text: str | None = None
    media_refs: list[IncomingMediaRef] = Field(default_factory=list)
    reply_to_message_id: str | None = None
    pending_process_id: str | None = None
    conversation_history_refs: list[str] = Field(default_factory=list)
    received_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PendingProcessRef(ChatModel):
    process_id: str
    kind: PendingProcessKind
    status: PendingProcessStatus = PendingProcessStatus.PENDING
    question: str | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PendingProcessContext(ChatModel):
    process_ref: PendingProcessRef
    context: dict[str, Any] = Field(default_factory=dict)
    conversation_history_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationSession(ChatModel):
    session_id: str = Field(default_factory=new_uuid)
    channel: ChatChannel
    external_conversation_id: str
    owner_id: str
    title: str = "New chat"
    status: ConversationStatus = ConversationStatus.ACTIVE
    active_pending_process_id: str | None = None
    last_message_at: datetime | None = None
    archived_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationMessage(ChatModel):
    message_id: str = Field(default_factory=new_uuid)
    session_id: str
    channel_message_id: str | None = None
    role: ConversationMessageRole
    text: str | None = None
    media_refs: list[IncomingMediaRef] = Field(default_factory=list)
    source_ref: str | None = None
    pending_process_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationHistoryItem(ChatModel):
    message_id: str
    role: ConversationMessageRole
    text: str | None = None
    pending_process_id: str | None = None
    created_at: datetime


class ChatAction(ChatModel):
    action_id: str = Field(default_factory=new_uuid)
    action_type: str
    label: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatEvidenceRef(ChatModel):
    evidence_id: str = Field(default_factory=new_uuid)
    title: str | None = None
    summary: str | None = None
    source_id: str | None = None
    node_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatDiagnostic(ChatModel):
    level: ChatDiagnosticLevel = ChatDiagnosticLevel.INFO
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(ChatModel):
    response_id: str = Field(default_factory=new_uuid)
    session_id: str
    status: ChatResponseStatus = ChatResponseStatus.OK
    primary_text: str
    pending_process: PendingProcessRef | None = None
    actions: list[ChatAction] = Field(default_factory=list)
    evidence: list[ChatEvidenceRef] = Field(default_factory=list)
    diagnostics: list[ChatDiagnostic] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ConversationSessionDetail(ChatModel):
    session: ConversationSession
    messages: list[ConversationMessage] = Field(default_factory=list)
    pending_process: PendingProcessContext | None = None
    pending_processes: list[PendingProcessContext] = Field(default_factory=list)


class ConversationSessionSummary(ChatModel):
    session_id: str
    channel: ChatChannel
    external_conversation_id: str
    owner_id: str
    title: str
    status: ConversationStatus
    active_pending_process_id: str | None = None
    pending_process_status: PendingProcessStatus | None = None
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationSessionList(ChatModel):
    sessions: list[ConversationSessionSummary] = Field(default_factory=list)
