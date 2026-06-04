from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select

from my_digital_brain.chat.enums import (
    ChatChannel,
    ConversationMessageRole,
    ConversationStatus,
    PendingProcessStatus,
)
from my_digital_brain.chat.exceptions import ChatNotFoundError
from my_digital_brain.chat.models import (
    ConversationMessage,
    ConversationSession,
    ConversationSessionDetail,
    ConversationSessionSummary,
    PendingProcessContext,
    PendingProcessRef,
    utc_now,
)
from my_digital_brain.chat.store import (
    _can_autotitle,
    _clean_title,
    _preview_text,
    _title_from_text,
)
from my_digital_brain.core.ids import new_uuid
from my_digital_brain.storage.relational import RelationalSessionProvider
from my_digital_brain.storage.relational_models import (
    ChatMessageRecord,
    ChatPendingProcessContextRecord,
    ChatSessionRecord,
)


class RelationalChatSessionStore:
    """SQLAlchemy-backed chat store for production web and Telegram chat."""

    def __init__(self, sessions: RelationalSessionProvider) -> None:
        self.sessions = sessions

    def create_session(
        self,
        *,
        channel: ChatChannel | str,
        owner_id: str,
        title: str | None = None,
        external_conversation_id: str | None = None,
        metadata: dict | None = None,
    ) -> ConversationSession:
        normalized_channel = ChatChannel(channel)
        session_id = new_uuid()
        external_id = external_conversation_id or session_id
        now = utc_now()
        record = ChatSessionRecord(
            id=session_id,
            created_at=now,
            updated_at=now,
            metadata_json={
                "title_source": "manual" if title else "default",
                **(metadata or {}),
            },
            channel=str(normalized_channel),
            external_conversation_id=external_id,
            owner_id=owner_id,
            title=_clean_title(title),
            status=ConversationStatus.ACTIVE.value,
            active_pending_process_id=None,
            last_message_at=None,
            archived_at=None,
        )
        with self.sessions.session() as db:
            db.add(record)
            db.flush()
            return _session_from_record(record)

    def get_or_create_session(
        self,
        *,
        channel: ChatChannel | str,
        external_conversation_id: str,
        owner_id: str,
    ) -> ConversationSession:
        normalized_channel = ChatChannel(channel)
        with self.sessions.session() as db:
            record = db.scalar(
                select(ChatSessionRecord).where(
                    ChatSessionRecord.channel == str(normalized_channel),
                    ChatSessionRecord.external_conversation_id == external_conversation_id,
                    ChatSessionRecord.owner_id == owner_id,
                ),
            )
            if record is not None:
                return _session_from_record(record)

            now = utc_now()
            record = ChatSessionRecord(
                id=new_uuid(),
                created_at=now,
                updated_at=now,
                metadata_json={"title_source": "default"},
                channel=str(normalized_channel),
                external_conversation_id=external_conversation_id,
                owner_id=owner_id,
                title="New chat",
                status=ConversationStatus.ACTIVE.value,
                active_pending_process_id=None,
                last_message_at=None,
                archived_at=None,
            )
            db.add(record)
            db.flush()
            return _session_from_record(record)

    def get_session(self, session_id: str) -> ConversationSession:
        with self.sessions.session() as db:
            record = db.get(ChatSessionRecord, session_id)
            if record is None:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            return _session_from_record(record)

    def save_session(self, session: ConversationSession) -> ConversationSession:
        with self.sessions.session() as db:
            record = db.get(ChatSessionRecord, session.session_id)
            if record is None:
                raise ChatNotFoundError(f"Chat session not found: {session.session_id}")
            _apply_session(record, session)
            record.updated_at = utc_now()
            db.flush()
            return _session_from_record(record)

    def list_sessions(
        self,
        *,
        owner_id: str,
        channel: ChatChannel | str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[ConversationSessionSummary]:
        normalized_channel = ChatChannel(channel) if channel is not None else None
        with self.sessions.session() as db:
            statement = select(ChatSessionRecord).where(ChatSessionRecord.owner_id == owner_id)
            if normalized_channel is not None:
                statement = statement.where(ChatSessionRecord.channel == str(normalized_channel))
            if not include_archived:
                statement = statement.where(
                    ChatSessionRecord.status != ConversationStatus.ARCHIVED.value,
                )
            statement = statement.order_by(
                desc(ChatSessionRecord.last_message_at),
                desc(ChatSessionRecord.updated_at),
            ).limit(max(0, limit))
            records = list(db.scalars(statement))
            return [self._summary_for_record(db, record) for record in records]

    def rename_session(self, session_id: str, title: str) -> ConversationSession:
        with self.sessions.session() as db:
            record = db.get(ChatSessionRecord, session_id)
            if record is None:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            record.title = _clean_title(title)
            record.metadata_json = {**(record.metadata_json or {}), "title_source": "manual"}
            record.updated_at = utc_now()
            db.flush()
            return _session_from_record(record)

    def archive_session(self, session_id: str) -> ConversationSession:
        with self.sessions.session() as db:
            record = db.get(ChatSessionRecord, session_id)
            if record is None:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            now = utc_now()
            record.status = ConversationStatus.ARCHIVED.value
            record.archived_at = now
            record.active_pending_process_id = None
            record.updated_at = now
            db.flush()
            return _session_from_record(record)

    def append_message(self, message: ConversationMessage) -> ConversationMessage:
        with self.sessions.session() as db:
            session = db.get(ChatSessionRecord, message.session_id)
            if session is None:
                raise ChatNotFoundError(f"Chat session not found: {message.session_id}")

            stored = message.model_copy(deep=True)
            record = ChatMessageRecord(
                id=stored.message_id,
                created_at=stored.created_at,
                updated_at=stored.created_at,
                metadata_json=stored.metadata,
                session_id=stored.session_id,
                channel_message_id=stored.channel_message_id,
                role=str(stored.role),
                text=stored.text,
                media_refs_json=[
                    media.model_dump(mode="json", exclude_none=True)
                    for media in stored.media_refs
                ],
                source_ref=stored.source_ref,
                pending_process_id=stored.pending_process_id,
            )
            db.add(record)

            if stored.role == ConversationMessageRole.USER or session.last_message_at is None:
                session.last_message_at = stored.created_at
                session.updated_at = utc_now()
                session_model = _session_from_record(session)
                if stored.role == ConversationMessageRole.USER and stored.text and _can_autotitle(
                    session_model,
                ):
                    session.title = _title_from_text(stored.text)
                    session.metadata_json = {
                        **(session.metadata_json or {}),
                        "title_source": "first_message",
                    }
            db.flush()
            return stored

    def list_messages(self, session_id: str, limit: int = 50) -> list[ConversationMessage]:
        with self.sessions.session() as db:
            if db.get(ChatSessionRecord, session_id) is None:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            records = list(
                db.scalars(
                    select(ChatMessageRecord)
                    .where(ChatMessageRecord.session_id == session_id)
                    .order_by(desc(ChatMessageRecord.created_at))
                    .limit(max(0, limit)),
                ),
            )
            return [_message_from_record(record) for record in reversed(records)]

    def get_session_detail(self, session_id: str, limit: int = 50) -> ConversationSessionDetail:
        return ConversationSessionDetail(
            session=self.get_session(session_id),
            messages=self.list_messages(session_id, limit=limit),
            pending_process=self.get_active_pending_process_context(session_id),
            pending_processes=self.list_pending_process_contexts(
                session_id,
                statuses={PendingProcessStatus.PENDING, PendingProcessStatus.PAUSED},
                limit=5,
            ),
        )

    def save_pending_process_context(
        self,
        session_id: str,
        context: PendingProcessContext,
    ) -> PendingProcessContext:
        with self.sessions.session() as db:
            session = db.get(ChatSessionRecord, session_id)
            if session is None:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")

            process_id = context.process_ref.process_id
            now = utc_now()
            record = db.get(ChatPendingProcessContextRecord, process_id)
            if record is None:
                record = ChatPendingProcessContextRecord(
                    id=process_id,
                    created_at=context.created_at,
                    updated_at=now,
                    metadata_json=context.metadata,
                    session_id=session_id,
                    kind=str(context.process_ref.kind),
                    status=str(context.process_ref.status),
                    question=context.process_ref.question,
                    expires_at=context.process_ref.expires_at,
                    process_metadata_json=context.process_ref.metadata,
                    context_json=context.context,
                    conversation_history_refs_json=context.conversation_history_refs,
                )
                db.add(record)
            else:
                _apply_pending_context(record, context, updated_at=now)

            if str(context.process_ref.status) == PendingProcessStatus.PENDING.value:
                session.active_pending_process_id = process_id
                session.updated_at = now
            db.flush()
            return _pending_from_record(record)

    def get_pending_process_context(self, process_id: str) -> PendingProcessContext:
        with self.sessions.session() as db:
            record = db.get(ChatPendingProcessContextRecord, process_id)
            if record is None:
                raise ChatNotFoundError(f"Pending process not found: {process_id}")
            return _pending_from_record(record)

    def get_active_pending_process_context(
        self,
        session_id: str,
    ) -> PendingProcessContext | None:
        with self.sessions.session() as db:
            session = db.get(ChatSessionRecord, session_id)
            if session is None:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            if session.active_pending_process_id is None:
                return None
            record = db.get(ChatPendingProcessContextRecord, session.active_pending_process_id)
            return _pending_from_record(record) if record is not None else None

    def list_pending_process_contexts(
        self,
        session_id: str,
        *,
        statuses: set[PendingProcessStatus | str] | None = None,
        limit: int = 5,
    ) -> list[PendingProcessContext]:
        normalized_statuses = (
            {str(getattr(status, "value", status)) for status in statuses}
            if statuses is not None
            else None
        )
        with self.sessions.session() as db:
            if db.get(ChatSessionRecord, session_id) is None:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            statement = select(ChatPendingProcessContextRecord).where(
                ChatPendingProcessContextRecord.session_id == session_id,
            )
            if normalized_statuses is not None:
                statement = statement.where(
                    ChatPendingProcessContextRecord.status.in_(normalized_statuses),
                )
            statement = statement.order_by(desc(ChatPendingProcessContextRecord.updated_at)).limit(
                max(0, limit),
            )
            return [_pending_from_record(record) for record in db.scalars(statement)]

    def update_pending_process_status(
        self,
        session_id: str,
        process_id: str,
        status: PendingProcessStatus | str,
        *,
        metadata: dict | None = None,
        context_updates: dict | None = None,
        activate: bool = False,
    ) -> PendingProcessContext:
        normalized_status = PendingProcessStatus(status)
        with self.sessions.session() as db:
            session = db.get(ChatSessionRecord, session_id)
            if session is None:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            record = db.get(ChatPendingProcessContextRecord, process_id)
            if record is None or record.session_id != session_id:
                raise ChatNotFoundError(f"Pending process not found: {process_id}")

            now = utc_now()
            record.status = normalized_status.value
            record.process_metadata_json = {
                **(record.process_metadata_json or {}),
                **(metadata or {}),
            }
            record.context_json = {**(record.context_json or {}), **(context_updates or {})}
            record.updated_at = now

            if activate:
                session.active_pending_process_id = process_id
            elif (
                session.active_pending_process_id == process_id
                and normalized_status != PendingProcessStatus.PENDING
            ):
                session.active_pending_process_id = None
            session.updated_at = now
            db.flush()
            return _pending_from_record(record)

    def clear_active_pending_process(self, session_id: str) -> ConversationSession:
        with self.sessions.session() as db:
            session = db.get(ChatSessionRecord, session_id)
            if session is None:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            session.active_pending_process_id = None
            session.updated_at = utc_now()
            db.flush()
            return _session_from_record(session)

    def expire_pending_processes(self, now: datetime | None = None) -> list[str]:
        reference_time = now or utc_now()
        with self.sessions.session() as db:
            records = list(
                db.scalars(
                    select(ChatPendingProcessContextRecord).where(
                        ChatPendingProcessContextRecord.expires_at.is_not(None),
                        ChatPendingProcessContextRecord.expires_at <= reference_time,
                        ChatPendingProcessContextRecord.status != PendingProcessStatus.EXPIRED.value,
                    ),
                ),
            )
            expired_ids = [record.id for record in records]
            for record in records:
                record.status = PendingProcessStatus.EXPIRED.value
                record.updated_at = reference_time
            for session in db.scalars(
                select(ChatSessionRecord).where(
                    ChatSessionRecord.active_pending_process_id.in_(expired_ids),
                ),
            ):
                session.active_pending_process_id = None
                session.updated_at = reference_time
            return expired_ids

    def _summary_for_record(self, db, record: ChatSessionRecord) -> ConversationSessionSummary:
        last_message = db.scalar(
            select(ChatMessageRecord)
            .where(
                ChatMessageRecord.session_id == record.id,
                ChatMessageRecord.role.in_(
                    [
                        ConversationMessageRole.USER.value,
                        ConversationMessageRole.ASSISTANT.value,
                    ],
                ),
            )
            .order_by(desc(ChatMessageRecord.created_at))
            .limit(1),
        )
        pending = (
            db.get(ChatPendingProcessContextRecord, record.active_pending_process_id)
            if record.active_pending_process_id
            else None
        )
        return ConversationSessionSummary(
            session_id=record.id,
            channel=record.channel,
            external_conversation_id=record.external_conversation_id,
            owner_id=record.owner_id,
            title=record.title,
            status=record.status,
            active_pending_process_id=record.active_pending_process_id,
            pending_process_status=pending.status if pending else None,
            last_message_preview=_preview_text(last_message.text if last_message else None),
            last_message_at=record.last_message_at,
            archived_at=record.archived_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
            metadata=record.metadata_json or {},
        )


def _session_from_record(record: ChatSessionRecord) -> ConversationSession:
    return ConversationSession(
        session_id=record.id,
        channel=record.channel,
        external_conversation_id=record.external_conversation_id,
        owner_id=record.owner_id,
        title=record.title,
        status=record.status,
        active_pending_process_id=record.active_pending_process_id,
        last_message_at=record.last_message_at,
        archived_at=record.archived_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
        metadata=record.metadata_json or {},
    )


def _apply_session(record: ChatSessionRecord, session: ConversationSession) -> None:
    record.channel = str(session.channel)
    record.external_conversation_id = session.external_conversation_id
    record.owner_id = session.owner_id
    record.title = session.title
    record.status = str(session.status)
    record.active_pending_process_id = session.active_pending_process_id
    record.last_message_at = session.last_message_at
    record.archived_at = session.archived_at
    record.metadata_json = session.metadata


def _message_from_record(record: ChatMessageRecord) -> ConversationMessage:
    return ConversationMessage(
        message_id=record.id,
        session_id=record.session_id,
        channel_message_id=record.channel_message_id,
        role=record.role,
        text=record.text,
        media_refs=list(record.media_refs_json or []),
        source_ref=record.source_ref,
        pending_process_id=record.pending_process_id,
        created_at=record.created_at,
        metadata=record.metadata_json or {},
    )


def _pending_from_record(record: ChatPendingProcessContextRecord) -> PendingProcessContext:
    return PendingProcessContext(
        process_ref=PendingProcessRef(
            process_id=record.id,
            kind=record.kind,
            status=record.status,
            question=record.question,
            expires_at=record.expires_at,
            metadata=record.process_metadata_json or {},
        ),
        context=record.context_json or {},
        conversation_history_refs=list(record.conversation_history_refs_json or []),
        created_at=record.created_at,
        updated_at=record.updated_at,
        metadata=record.metadata_json or {},
    )


def _apply_pending_context(
    record: ChatPendingProcessContextRecord,
    context: PendingProcessContext,
    *,
    updated_at: datetime,
) -> None:
    record.updated_at = updated_at
    record.metadata_json = context.metadata
    record.kind = str(context.process_ref.kind)
    record.status = str(context.process_ref.status)
    record.question = context.process_ref.question
    record.expires_at = context.process_ref.expires_at
    record.process_metadata_json = context.process_ref.metadata
    record.context_json = context.context
    record.conversation_history_refs_json = context.conversation_history_refs
