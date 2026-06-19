from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class TelegramChat(TimestampMixin, Base):
    __tablename__ = "telegram_chats"

    chat_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ChatSessionRecord(TimestampMixin, Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        UniqueConstraint(
            "channel",
            "external_conversation_id",
            "owner_id",
            name="uq_chat_sessions_channel_external_owner",
        ),
    )

    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    external_conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    active_pending_process_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    active_agentic_frame_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatMessageRecord(TimestampMixin, Base):
    __tablename__ = "chat_messages"

    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    channel_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_refs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pending_process_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class ChatPendingProcessContextRecord(TimestampMixin, Base):
    __tablename__ = "chat_pending_process_contexts"

    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    process_metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    context_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    conversation_history_refs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class ChatAgenticFrameRecord(TimestampMixin, Base):
    __tablename__ = "chat_agentic_frames"

    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    state_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    messages_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    context_payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    compact_trace_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    parent_frame_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    parent_tool_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_tool_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    clarification_packet_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IngestionSession(TimestampMixin, Base):
    __tablename__ = "ingestion_sessions"

    telegram_chat_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    pending_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_graph_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SourceRecord(TimestampMixin, Base):
    __tablename__ = "source_records"

    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    derived_from_source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ProviderRequestLog(TimestampMixin, Base):
    __tablename__ = "provider_request_logs"

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    operation: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    privacy_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_estimate: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)


class RegistryRecord(TimestampMixin):
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)


class ModelRegistry(TimestampMixin, Base):
    __tablename__ = "model_registry"

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    capability: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)


class PromptRegistry(RegistryRecord, Base):
    __tablename__ = "prompt_registry"


class SchemaRegistry(RegistryRecord, Base):
    __tablename__ = "schema_registry"


class BackgroundJob(TimestampMixin, Base):
    __tablename__ = "background_jobs"

    job_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class VectorRecord(TimestampMixin, Base):
    __tablename__ = "vector_records"

    vector_store: Mapped[str] = mapped_column(String(64), nullable=False)
    collection: Mapped[str] = mapped_column(String(128), nullable=False)
    vector_id: Mapped[str] = mapped_column(String(255), nullable=False)
    graph_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    embedding_scope: Mapped[str | None] = mapped_column(String(128), nullable=True)
    primary_target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    primary_target_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    related_target_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    relationship_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    builder_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    document_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class BackupExport(TimestampMixin, Base):
    __tablename__ = "backup_exports"

    status: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    export_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    encrypted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_log"

    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
