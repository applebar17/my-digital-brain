from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Protocol

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


class ChatSessionStore(Protocol):
    def create_session(
        self,
        *,
        channel: ChatChannel | str,
        owner_id: str,
        title: str | None = None,
        external_conversation_id: str | None = None,
        metadata: dict | None = None,
    ) -> ConversationSession: ...

    def get_or_create_session(
        self,
        *,
        channel: ChatChannel | str,
        external_conversation_id: str,
        owner_id: str,
    ) -> ConversationSession: ...

    def get_session(self, session_id: str) -> ConversationSession: ...

    def save_session(self, session: ConversationSession) -> ConversationSession: ...

    def list_sessions(
        self,
        *,
        owner_id: str,
        channel: ChatChannel | str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[ConversationSessionSummary]: ...

    def rename_session(self, session_id: str, title: str) -> ConversationSession: ...

    def archive_session(self, session_id: str) -> ConversationSession: ...

    def append_message(self, message: ConversationMessage) -> ConversationMessage: ...

    def list_messages(self, session_id: str, limit: int = 50) -> list[ConversationMessage]: ...

    def get_session_detail(self, session_id: str, limit: int = 50) -> ConversationSessionDetail: ...

    def save_agentic_frame(self, session_id: str, frame: AgenticFrame) -> AgenticFrame: ...

    def get_agentic_frame(self, frame_id: str) -> AgenticFrame: ...

    def get_active_agentic_frame(self, session_id: str) -> AgenticFrame | None: ...

    def list_agentic_frames(
        self,
        session_id: str,
        *,
        statuses: set[str] | None = None,
        limit: int = 5,
    ) -> list[AgenticFrame]: ...

    def update_agentic_frame_status(
        self,
        session_id: str,
        frame_id: str,
        status: str,
        *,
        metadata: dict | None = None,
        messages: list[dict] | None = None,
        clarification_packet: dict | None = None,
    ) -> AgenticFrame: ...


class InMemoryChatSessionStore:
    """Local development store for chat runtime behavior."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._sessions: dict[str, ConversationSession] = {}
        self._session_keys: dict[tuple[str, str, str], str] = {}
        self._messages: dict[str, list[ConversationMessage]] = defaultdict(list)
        self._agentic_frames: dict[str, AgenticFrame] = {}
        self._agentic_frame_session_ids: dict[str, set[str]] = defaultdict(set)

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
        with self._lock:
            session = ConversationSession(
                channel=normalized_channel,
                external_conversation_id=external_conversation_id or "",
                owner_id=owner_id,
                title=_clean_title(title),
                metadata={"title_source": "manual" if title else "default", **(metadata or {})},
            )
            if not session.external_conversation_id:
                session = session.model_copy(
                    update={"external_conversation_id": session.session_id},
                    deep=True,
                )
            key = (str(normalized_channel), session.external_conversation_id, owner_id)
            if key in self._session_keys:
                raise ChatNotFoundError(
                    "A chat session already exists for this external conversation id.",
                )
            self._sessions[session.session_id] = session
            self._session_keys[key] = session.session_id
            return self._copy_session(session)

    def get_or_create_session(
        self,
        *,
        channel: ChatChannel | str,
        external_conversation_id: str,
        owner_id: str,
    ) -> ConversationSession:
        normalized_channel = ChatChannel(channel)
        key = (str(normalized_channel), external_conversation_id, owner_id)
        with self._lock:
            existing_session_id = self._session_keys.get(key)
            if existing_session_id is not None:
                return self._copy_session(self._sessions[existing_session_id])

            session = ConversationSession(
                channel=normalized_channel,
                external_conversation_id=external_conversation_id,
                owner_id=owner_id,
                metadata={"title_source": "default"},
            )
            self._sessions[session.session_id] = session
            self._session_keys[key] = session.session_id
            return self._copy_session(session)

    def get_session(self, session_id: str) -> ConversationSession:
        with self._lock:
            try:
                return self._copy_session(self._sessions[session_id])
            except KeyError as exc:
                raise ChatNotFoundError(f"Chat session not found: {session_id}") from exc

    def save_session(self, session: ConversationSession) -> ConversationSession:
        with self._lock:
            if session.session_id not in self._sessions:
                raise ChatNotFoundError(f"Chat session not found: {session.session_id}")
            updated = session.model_copy(update={"updated_at": utc_now()}, deep=True)
            self._sessions[updated.session_id] = updated
            return self._copy_session(updated)

    def list_sessions(
        self,
        *,
        owner_id: str,
        channel: ChatChannel | str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[ConversationSessionSummary]:
        normalized_channel = ChatChannel(channel) if channel is not None else None
        with self._lock:
            sessions = [
                session
                for session in self._sessions.values()
                if session.owner_id == owner_id
                and (normalized_channel is None or session.channel == normalized_channel)
                and (include_archived or session.status != ConversationStatus.ARCHIVED)
            ]
            sessions.sort(
                key=lambda item: item.last_message_at or item.updated_at or item.created_at,
                reverse=True,
            )
            return [
                self._summary_for_session(session)
                for session in sessions[: max(0, limit)]
            ]

    def rename_session(self, session_id: str, title: str) -> ConversationSession:
        with self._lock:
            session = self.get_session(session_id)
            updated = session.model_copy(
                update={
                    "title": _clean_title(title),
                    "metadata": {**session.metadata, "title_source": "manual"},
                    "updated_at": utc_now(),
                },
                deep=True,
            )
            self._sessions[session_id] = updated
            return self._copy_session(updated)

    def archive_session(self, session_id: str) -> ConversationSession:
        with self._lock:
            session = self.get_session(session_id)
            updated = session.model_copy(
                update={
                    "status": ConversationStatus.ARCHIVED,
                    "archived_at": utc_now(),
                    "updated_at": utc_now(),
                },
                deep=True,
            )
            self._sessions[session_id] = updated
            return self._copy_session(updated)

    def append_message(self, message: ConversationMessage) -> ConversationMessage:
        with self._lock:
            if message.session_id not in self._sessions:
                raise ChatNotFoundError(f"Chat session not found: {message.session_id}")

            stored = message.model_copy(deep=True)
            self._messages[stored.session_id].append(stored)

            session = self._sessions[stored.session_id]
            timestamp = stored.created_at
            if stored.role == ConversationMessageRole.USER or session.last_message_at is None:
                session_update = {
                    "last_message_at": timestamp,
                    "updated_at": utc_now(),
                }
                if (
                    stored.role == ConversationMessageRole.USER
                    and stored.text
                    and _can_autotitle(session)
                ):
                    session_update["title"] = _title_from_text(stored.text)
                    session_update["metadata"] = {
                        **session.metadata,
                        "title_source": "first_message",
                    }
                session = session.model_copy(
                    update=session_update,
                    deep=True,
                )
                self._sessions[session.session_id] = session

            return stored.model_copy(deep=True)

    def list_messages(self, session_id: str, limit: int = 50) -> list[ConversationMessage]:
        with self._lock:
            if session_id not in self._sessions:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            selected = self._messages[session_id][-limit:]
            return [message.model_copy(deep=True) for message in selected]

    def get_session_detail(self, session_id: str, limit: int = 50) -> ConversationSessionDetail:
        return ConversationSessionDetail(
            session=self.get_session(session_id),
            messages=self.list_messages(session_id, limit=limit),
            active_agentic_frame=self.get_active_agentic_frame(session_id),
        )

    def save_agentic_frame(self, session_id: str, frame: AgenticFrame) -> AgenticFrame: ...

    def get_agentic_frame(self, frame_id: str) -> AgenticFrame: ...

    def get_active_agentic_frame(self, session_id: str) -> AgenticFrame | None: ...

    def list_agentic_frames(
        self,
        session_id: str,
        *,
        statuses: set[str] | None = None,
        limit: int = 5,
    ) -> list[AgenticFrame]: ...

    def update_agentic_frame_status(
        self,
        session_id: str,
        frame_id: str,
        status: str,
        *,
        metadata: dict | None = None,
        messages: list[dict] | None = None,
        clarification_packet: dict | None = None,
    ) -> AgenticFrame: ...


class InMemoryChatSessionStore:
    """Local development store for chat runtime behavior."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._sessions: dict[str, ConversationSession] = {}
        self._session_keys: dict[tuple[str, str, str], str] = {}
        self._messages: dict[str, list[ConversationMessage]] = defaultdict(list)
        self._agentic_frames: dict[str, AgenticFrame] = {}
        self._agentic_frame_session_ids: dict[str, set[str]] = defaultdict(set)

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
        with self._lock:
            session = ConversationSession(
                channel=normalized_channel,
                external_conversation_id=external_conversation_id or "",
                owner_id=owner_id,
                title=_clean_title(title),
                metadata={"title_source": "manual" if title else "default", **(metadata or {})},
            )
            if not session.external_conversation_id:
                session = session.model_copy(
                    update={"external_conversation_id": session.session_id},
                    deep=True,
                )
            key = (str(normalized_channel), session.external_conversation_id, owner_id)
            if key in self._session_keys:
                raise ChatNotFoundError(
                    "A chat session already exists for this external conversation id.",
                )
            self._sessions[session.session_id] = session
            self._session_keys[key] = session.session_id
            return self._copy_session(session)

    def get_or_create_session(
        self,
        *,
        channel: ChatChannel | str,
        external_conversation_id: str,
        owner_id: str,
    ) -> ConversationSession:
        normalized_channel = ChatChannel(channel)
        key = (str(normalized_channel), external_conversation_id, owner_id)
        with self._lock:
            existing_session_id = self._session_keys.get(key)
            if existing_session_id is not None:
                return self._copy_session(self._sessions[existing_session_id])

            session = ConversationSession(
                channel=normalized_channel,
                external_conversation_id=external_conversation_id,
                owner_id=owner_id,
                metadata={"title_source": "default"},
            )
            self._sessions[session.session_id] = session
            self._session_keys[key] = session.session_id
            return self._copy_session(session)

    def get_session(self, session_id: str) -> ConversationSession:
        with self._lock:
            try:
                return self._copy_session(self._sessions[session_id])
            except KeyError as exc:
                raise ChatNotFoundError(f"Chat session not found: {session_id}") from exc

    def save_session(self, session: ConversationSession) -> ConversationSession:
        with self._lock:
            if session.session_id not in self._sessions:
                raise ChatNotFoundError(f"Chat session not found: {session.session_id}")
            updated = session.model_copy(update={"updated_at": utc_now()}, deep=True)
            self._sessions[updated.session_id] = updated
            return self._copy_session(updated)

    def list_sessions(
        self,
        *,
        owner_id: str,
        channel: ChatChannel | str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[ConversationSessionSummary]:
        normalized_channel = ChatChannel(channel) if channel is not None else None
        with self._lock:
            sessions = [
                session
                for session in self._sessions.values()
                if session.owner_id == owner_id
                and (normalized_channel is None or session.channel == normalized_channel)
                and (include_archived or session.status != ConversationStatus.ARCHIVED)
            ]
            sessions.sort(
                key=lambda item: item.last_message_at or item.updated_at or item.created_at,
                reverse=True,
            )
            return [
                self._summary_for_session(session)
                for session in sessions[: max(0, limit)]
            ]

    def rename_session(self, session_id: str, title: str) -> ConversationSession:
        with self._lock:
            session = self.get_session(session_id)
            updated = session.model_copy(
                update={
                    "title": _clean_title(title),
                    "metadata": {**session.metadata, "title_source": "manual"},
                    "updated_at": utc_now(),
                },
                deep=True,
            )
            self._sessions[session_id] = updated
            return self._copy_session(updated)

    def archive_session(self, session_id: str) -> ConversationSession:
        with self._lock:
            session = self.get_session(session_id)
            updated = session.model_copy(
                update={
                    "status": ConversationStatus.ARCHIVED,
                    "archived_at": utc_now(),
                    "updated_at": utc_now(),
                },
                deep=True,
            )
            self._sessions[session_id] = updated
            return self._copy_session(updated)

    def append_message(self, message: ConversationMessage) -> ConversationMessage:
        with self._lock:
            if message.session_id not in self._sessions:
                raise ChatNotFoundError(f"Chat session not found: {message.session_id}")

            stored = message.model_copy(deep=True)
            self._messages[stored.session_id].append(stored)

            session = self._sessions[stored.session_id]
            timestamp = stored.created_at
            if stored.role == ConversationMessageRole.USER or session.last_message_at is None:
                session_update = {
                    "last_message_at": timestamp,
                    "updated_at": utc_now(),
                }
                if (
                    stored.role == ConversationMessageRole.USER
                    and stored.text
                    and _can_autotitle(session)
                ):
                    session_update["title"] = _title_from_text(stored.text)
                    session_update["metadata"] = {
                        **session.metadata,
                        "title_source": "first_message",
                    }
                session = session.model_copy(
                    update=session_update,
                    deep=True,
                )
                self._sessions[session.session_id] = session

            return stored.model_copy(deep=True)

    def list_messages(self, session_id: str, limit: int = 50) -> list[ConversationMessage]:
        with self._lock:
            if session_id not in self._sessions:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            selected = self._messages[session_id][-limit:]
            return [message.model_copy(deep=True) for message in selected]

    def get_session_detail(self, session_id: str, limit: int = 50) -> ConversationSessionDetail:
        return ConversationSessionDetail(
            session=self.get_session(session_id),
            messages=self.list_messages(session_id, limit=limit),
            active_agentic_frame=self.get_active_agentic_frame(session_id),
        )

    def save_agentic_frame(self, session_id: str, frame: AgenticFrame) -> AgenticFrame:
        with self._lock:
            if session_id not in self._sessions:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            updated = frame.model_copy(
                update={"session_id": session_id, "updated_at": utc_now()},
                deep=True,
            )
            self._agentic_frames[updated.frame_id] = updated
            self._agentic_frame_session_ids[session_id].add(updated.frame_id)
            self._sync_session_active_frame(session_id)
            return updated.model_copy(deep=True)

    def get_agentic_frame(self, frame_id: str) -> AgenticFrame:
        with self._lock:
            try:
                return self._agentic_frames[frame_id].model_copy(deep=True)
            except KeyError as exc:
                raise ChatNotFoundError(f"Agentic frame not found: {frame_id}") from exc

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
        with self._lock:
            if session_id not in self._sessions:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            normalized_statuses = {str(status) for status in statuses} if statuses else None
            frames: list[AgenticFrame] = []
            for frame_id in self._agentic_frame_session_ids.get(session_id, set()):
                frame = self._agentic_frames.get(frame_id)
                if frame is None:
                    continue
                if normalized_statuses is not None and frame.status not in normalized_statuses:
                    continue
                frames.append(frame.model_copy(deep=True))
            frames.sort(key=lambda item: item.updated_at, reverse=True)
            return frames[: max(0, limit)]

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
        with self._lock:
            if session_id not in self._sessions:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            frame = self.get_agentic_frame(frame_id)
            if frame.session_id != session_id:
                raise ChatNotFoundError(f"Agentic frame not found: {frame_id}")
            update: dict[str, object] = {
                "status": status,
                "updated_at": utc_now(),
                "metadata": {**frame.metadata, **(metadata or {})},
            }
            if messages is not None:
                update["messages"] = messages
            if clarification_packet is not None:
                update["clarification_packet"] = ClarificationPacket.model_validate(
                    clarification_packet,
                )
            updated = frame.model_copy(update=update, deep=True)
            self._agentic_frames[frame_id] = updated
            self._sync_session_active_frame(session_id)
            return updated.model_copy(deep=True)

    def _sync_session_active_frame(self, session_id: str) -> None:
        active = [
            frame
            for frame_id in self._agentic_frame_session_ids.get(session_id, set())
            if (frame := self._agentic_frames.get(frame_id)) is not None
            and frame.status == "interrupted"
        ]
        active.sort(key=lambda item: item.updated_at, reverse=True)
        session = self._sessions[session_id]
        self._sessions[session_id] = session.model_copy(
            update={
                "active_agentic_frame_id": active[0].frame_id if active else None,
                "updated_at": utc_now(),
            },
            deep=True,
        )

    @staticmethod
    def _copy_session(session: ConversationSession) -> ConversationSession:
        return session.model_copy(deep=True)

    def _summary_for_session(self, session: ConversationSession) -> ConversationSessionSummary:
        messages = self._messages.get(session.session_id, [])
        last_text = next(
            (
                message.text
                for message in reversed(messages)
                if message.text
                and message.role
                in {ConversationMessageRole.USER, ConversationMessageRole.ASSISTANT}
                and not _is_ui_hidden_message(message.metadata)
            ),
            None,
        )
        return ConversationSessionSummary(
            session_id=session.session_id,
            channel=session.channel,
            external_conversation_id=session.external_conversation_id,
            owner_id=session.owner_id,
            title=session.title,
            status=session.status,
            active_agentic_frame_id=session.active_agentic_frame_id,
            last_message_preview=_preview_text(last_text),
            last_message_at=session.last_message_at,
            archived_at=session.archived_at,
            created_at=session.created_at,
            updated_at=session.updated_at,
            metadata=session.metadata,
        )


def _clean_title(title: str | None) -> str:
    cleaned = (title or "New chat").strip()
    if not cleaned:
        cleaned = "New chat"
    return cleaned[:120]


def _title_from_text(text: str) -> str:
    return _preview_text(text, limit=46) or "New chat"


def _preview_text(text: str | None, *, limit: int = 120) -> str | None:
    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return None
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3] + "..."


def _is_ui_hidden_message(metadata: dict) -> bool:
    if metadata.get("ui_hidden") is True:
        return True
    return metadata.get("message_kind") in {
        "clarification_prompt",
        "clarification_answer",
    }


def _can_autotitle(session: ConversationSession) -> bool:
    return (
        session.title == "New chat"
        and str(session.metadata.get("title_source") or "default") != "manual"
    )
