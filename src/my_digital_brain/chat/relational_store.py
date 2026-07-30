from __future__ import annotations

from sqlalchemy import desc, select

from my_digital_brain.chat.enums import (
    ChatChannel,
    ConversationMessageRole,
    ConversationStatus,
)
from my_digital_brain.chat.exceptions import ChatNotFoundError
from my_digital_brain.chat.models import (
    AgenticFrame,
    ConversationMessage,
    ConversationSession,
    ConversationSessionDetail,
    ConversationSessionSummary,
    utc_now,
)
from my_digital_brain.clarification.contracts import ClarificationPacket
from my_digital_brain.chat.store import (
    _can_autotitle,
    _clean_title,
    _is_ui_hidden_message,
    _preview_text,
    _title_from_text,
)
from my_digital_brain.core.ids import new_uuid
from my_digital_brain.storage.relational import RelationalSessionProvider
from my_digital_brain.storage.relational_models import (
    ChatAgenticFrameRecord,
    ChatMessageRecord,
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
            active_agentic_frame_id=None,
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
                    active_agentic_frame_id=None,
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
            record.active_agentic_frame_id = None
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
            active_agentic_frame=self.get_active_agentic_frame(session_id),
        )

    def save_agentic_frame(self, session_id: str, frame: AgenticFrame) -> AgenticFrame:
        with self.sessions.session() as db:
            session = db.get(ChatSessionRecord, session_id)
            if session is None:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            now = utc_now()
            record = db.get(ChatAgenticFrameRecord, frame.frame_id)
            if record is None:
                record = ChatAgenticFrameRecord(
                    id=frame.frame_id,
                    created_at=frame.created_at,
                    updated_at=now,
                    metadata_json=frame.metadata,
                    session_id=session_id,
                    state_id=frame.state_id,
                    status=frame.status,
                    messages_json=frame.messages,
                    context_payload_json=frame.context_payload,
                    compact_trace_json=frame.compact_trace,
                    parent_frame_id=frame.parent_frame_id,
                    parent_tool_call_id=frame.parent_tool_call_id,
                    active_tool_call_id=frame.active_tool_call_id,
                    active_tool_name=frame.active_tool_name,
                    clarification_packet_json=(
                        frame.clarification_packet.model_dump(mode="json", exclude_none=True)
                        if frame.clarification_packet is not None
                        else None
                    ),
                    expires_at=frame.expires_at,
                )
                db.add(record)
            else:
                _apply_agentic_frame(record, frame, updated_at=now)
            db.flush()
            self._sync_active_agentic_frame(db, session_id)
            db.flush()
            return _agentic_frame_from_record(record)

    def get_agentic_frame(self, frame_id: str) -> AgenticFrame:
        with self.sessions.session() as db:
            record = db.get(ChatAgenticFrameRecord, frame_id)
            if record is None:
                raise ChatNotFoundError(f"Agentic frame not found: {frame_id}")
            return _agentic_frame_from_record(record)

    def get_active_agentic_frame(self, session_id: str) -> AgenticFrame | None:
        frames = self.list_agentic_frames(session_id, statuses={"interrupted"}, limit=1)
        return frames[0] if frames else None

    def list_agentic_frames(
        self,
        session_id: str,
        *,
        statuses: set[str] | None = None,
        limit: int = 5,
    ) -> list[AgenticFrame]:
        normalized_statuses = {str(status) for status in statuses} if statuses else None
        with self.sessions.session() as db:
            if db.get(ChatSessionRecord, session_id) is None:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            statement = select(ChatAgenticFrameRecord).where(
                ChatAgenticFrameRecord.session_id == session_id,
            )
            if normalized_statuses is not None:
                statement = statement.where(
                    ChatAgenticFrameRecord.status.in_(normalized_statuses),
                )
            statement = statement.order_by(desc(ChatAgenticFrameRecord.updated_at)).limit(
                max(0, limit),
            )
            return [_agentic_frame_from_record(record) for record in db.scalars(statement)]

    def update_agentic_frame_status(
        self,
        session_id: str,
        frame_id: str,
        status: str,
        *,
        metadata: dict | None = None,
        messages: list[dict] | None = None,
        clarification_packet: dict | None = None,
    ) -> AgenticFrame:
        with self.sessions.session() as db:
            if db.get(ChatSessionRecord, session_id) is None:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            record = db.get(ChatAgenticFrameRecord, frame_id)
            if record is None or record.session_id != session_id:
                raise ChatNotFoundError(f"Agentic frame not found: {frame_id}")
            record.status = status
            record.updated_at = utc_now()
            record.metadata_json = {**(record.metadata_json or {}), **(metadata or {})}
            if messages is not None:
                record.messages_json = messages
            if clarification_packet is not None:
                record.clarification_packet_json = clarification_packet
            db.flush()
            self._sync_active_agentic_frame(db, session_id)
            db.flush()
            return _agentic_frame_from_record(record)

    def _summary_for_record(self, db, record: ChatSessionRecord) -> ConversationSessionSummary:
        recent_messages = list(
            db.scalars(
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
                .limit(20),
            )
        )
        last_message = next(
            (
                message
                for message in recent_messages
                if not _is_ui_hidden_message(message.metadata_json or {})
            ),
            None,
        )
        return ConversationSessionSummary(
            session_id=record.id,
            channel=record.channel,
            external_conversation_id=record.external_conversation_id,
            owner_id=record.owner_id,
            title=record.title,
            status=record.status,
            active_agentic_frame_id=record.active_agentic_frame_id,
            last_message_preview=_preview_text(last_message.text if last_message else None),
            last_message_at=record.last_message_at,
            archived_at=record.archived_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
            metadata=record.metadata_json or {},
        )

    def _sync_active_agentic_frame(self, db, session_id: str) -> None:
        session = db.get(ChatSessionRecord, session_id)
        if session is None:
            raise ChatNotFoundError(f"Chat session not found: {session_id}")
        active = db.scalar(
            select(ChatAgenticFrameRecord)
            .where(
                ChatAgenticFrameRecord.session_id == session_id,
                ChatAgenticFrameRecord.status == "interrupted",
            )
            .order_by(desc(ChatAgenticFrameRecord.updated_at))
            .limit(1),
        )
        session.active_agentic_frame_id = active.id if active is not None else None
        session.updated_at = utc_now()


def _session_from_record(record: ChatSessionRecord) -> ConversationSession:
    return ConversationSession(
        session_id=record.id,
        channel=record.channel,
        external_conversation_id=record.external_conversation_id,
        owner_id=record.owner_id,
        title=record.title,
        status=record.status,
        active_agentic_frame_id=record.active_agentic_frame_id,
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
    record.active_agentic_frame_id = session.active_agentic_frame_id
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
        created_at=record.created_at,
        metadata=record.metadata_json or {},
    )


def _agentic_frame_from_record(record: ChatAgenticFrameRecord) -> AgenticFrame:
    packet = (
        ClarificationPacket.model_validate(record.clarification_packet_json)
        if isinstance(record.clarification_packet_json, dict)
        else None
    )
    return AgenticFrame(
        frame_id=record.id,
        session_id=record.session_id,
        state_id=record.state_id,
        status=record.status,
        messages=list(record.messages_json or []),
        context_payload=record.context_payload_json or {},
        compact_trace=list(record.compact_trace_json or []),
        parent_frame_id=record.parent_frame_id,
        parent_tool_call_id=record.parent_tool_call_id,
        active_tool_call_id=record.active_tool_call_id,
        active_tool_name=record.active_tool_name,
        clarification_packet=packet,
        expires_at=record.expires_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
        metadata=record.metadata_json or {},
    )


def _apply_agentic_frame(
    record: ChatAgenticFrameRecord,
    frame: AgenticFrame,
    *,
    updated_at: datetime,
) -> None:
    record.updated_at = updated_at
    record.metadata_json = frame.metadata
    record.session_id = frame.session_id
    record.state_id = frame.state_id
    record.status = frame.status
    record.messages_json = frame.messages
    record.context_payload_json = frame.context_payload
    record.compact_trace_json = frame.compact_trace
    record.parent_frame_id = frame.parent_frame_id
    record.parent_tool_call_id = frame.parent_tool_call_id
    record.active_tool_call_id = frame.active_tool_call_id
    record.active_tool_name = frame.active_tool_name
    record.clarification_packet_json = (
        frame.clarification_packet.model_dump(mode="json", exclude_none=True)
        if frame.clarification_packet is not None
        else None
    )
    record.expires_at = frame.expires_at
