from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from threading import RLock
from typing import Protocol

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
    utc_now,
)


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

    def save_pending_process_context(
        self,
        session_id: str,
        context: PendingProcessContext,
    ) -> PendingProcessContext: ...

    def get_pending_process_context(self, process_id: str) -> PendingProcessContext: ...

    def get_active_pending_process_context(
        self,
        session_id: str,
    ) -> PendingProcessContext | None: ...

    def list_pending_process_contexts(
        self,
        session_id: str,
        *,
        statuses: set[PendingProcessStatus | str] | None = None,
        limit: int = 5,
    ) -> list[PendingProcessContext]: ...

    def update_pending_process_status(
        self,
        session_id: str,
        process_id: str,
        status: PendingProcessStatus | str,
        *,
        metadata: dict | None = None,
        context_updates: dict | None = None,
        activate: bool = False,
    ) -> PendingProcessContext: ...

    def clear_active_pending_process(self, session_id: str) -> ConversationSession: ...

    def expire_pending_processes(self, now: datetime | None = None) -> list[str]: ...


class InMemoryChatSessionStore:
    """Local development store for chat runtime behavior."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._sessions: dict[str, ConversationSession] = {}
        self._session_keys: dict[tuple[str, str, str], str] = {}
        self._messages: dict[str, list[ConversationMessage]] = defaultdict(list)
        self._pending_contexts: dict[str, PendingProcessContext] = {}
        self._pending_session_ids: dict[str, set[str]] = defaultdict(set)

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
                    "active_pending_process_id": None,
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
        session = self.get_session(session_id)
        messages = self.list_messages(session_id, limit=limit)
        pending = self.get_active_pending_process_context(session_id)
        pending_processes = self.list_pending_process_contexts(
            session_id,
            statuses={PendingProcessStatus.PENDING, PendingProcessStatus.PAUSED},
            limit=5,
        )
        return ConversationSessionDetail(
            session=session,
            messages=messages,
            pending_process=pending,
            pending_processes=pending_processes,
        )

    def save_pending_process_context(
        self,
        session_id: str,
        context: PendingProcessContext,
    ) -> PendingProcessContext:
        with self._lock:
            if session_id not in self._sessions:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")

            updated_context = context.model_copy(update={"updated_at": utc_now()}, deep=True)
            self._pending_contexts[updated_context.process_ref.process_id] = updated_context
            self._pending_session_ids[session_id].add(updated_context.process_ref.process_id)

            if updated_context.process_ref.status == PendingProcessStatus.PENDING.value:
                session = self._sessions[session_id].model_copy(
                    update={
                        "active_pending_process_id": updated_context.process_ref.process_id,
                        "updated_at": utc_now(),
                    },
                    deep=True,
                )
                self._sessions[session_id] = session
            return updated_context.model_copy(deep=True)

    def get_pending_process_context(self, process_id: str) -> PendingProcessContext:
        with self._lock:
            try:
                return self._pending_contexts[process_id].model_copy(deep=True)
            except KeyError as exc:
                raise ChatNotFoundError(f"Pending process not found: {process_id}") from exc

    def get_active_pending_process_context(
        self,
        session_id: str,
    ) -> PendingProcessContext | None:
        with self._lock:
            session = self.get_session(session_id)
            if session.active_pending_process_id is None:
                return None
            context = self._pending_contexts.get(session.active_pending_process_id)
            return context.model_copy(deep=True) if context is not None else None

    def list_pending_process_contexts(
        self,
        session_id: str,
        *,
        statuses: set[PendingProcessStatus | str] | None = None,
        limit: int = 5,
    ) -> list[PendingProcessContext]:
        with self._lock:
            if session_id not in self._sessions:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            normalized_statuses = (
                {str(getattr(status, "value", status)) for status in statuses}
                if statuses is not None
                else None
            )
            contexts: list[PendingProcessContext] = []
            for process_id in self._pending_session_ids.get(session_id, set()):
                context = self._pending_contexts.get(process_id)
                if context is None:
                    continue
                if (
                    normalized_statuses is not None
                    and str(context.process_ref.status) not in normalized_statuses
                ):
                    continue
                contexts.append(context.model_copy(deep=True))
            contexts.sort(key=lambda item: item.updated_at, reverse=True)
            return contexts[: max(0, limit)]

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
        with self._lock:
            if session_id not in self._sessions:
                raise ChatNotFoundError(f"Chat session not found: {session_id}")
            if process_id not in self._pending_session_ids.get(session_id, set()):
                raise ChatNotFoundError(f"Pending process not found: {process_id}")
            context = self.get_pending_process_context(process_id)
            normalized_status = PendingProcessStatus(status)
            updated_ref = context.process_ref.model_copy(
                update={
                    "status": normalized_status.value,
                    "metadata": {
                        **context.process_ref.metadata,
                        **(metadata or {}),
                    },
                },
                deep=True,
            )
            updated_context = context.model_copy(
                update={
                    "process_ref": updated_ref,
                    "context": {
                        **context.context,
                        **(context_updates or {}),
                    },
                    "updated_at": utc_now(),
                },
                deep=True,
            )
            self._pending_contexts[process_id] = updated_context

            session = self._sessions[session_id]
            active_process_id = session.active_pending_process_id
            if activate:
                active_process_id = process_id
            elif active_process_id == process_id and normalized_status != PendingProcessStatus.PENDING:
                active_process_id = None
            self._sessions[session_id] = session.model_copy(
                update={
                    "active_pending_process_id": active_process_id,
                    "updated_at": utc_now(),
                },
                deep=True,
            )
            return updated_context.model_copy(deep=True)

    def clear_active_pending_process(self, session_id: str) -> ConversationSession:
        with self._lock:
            session = self.get_session(session_id)
            updated = session.model_copy(
                update={"active_pending_process_id": None, "updated_at": utc_now()},
                deep=True,
            )
            self._sessions[session_id] = updated
            return updated.model_copy(deep=True)

    def expire_pending_processes(self, now: datetime | None = None) -> list[str]:
        reference_time = now or utc_now()
        expired_ids: list[str] = []
        with self._lock:
            for process_id, context in list(self._pending_contexts.items()):
                expires_at = context.process_ref.expires_at
                if expires_at is not None and expires_at <= reference_time:
                    expired_ids.append(process_id)
                    del self._pending_contexts[process_id]

            if expired_ids:
                expired = set(expired_ids)
                for session_id, session in list(self._sessions.items()):
                    if session.active_pending_process_id in expired:
                        self._sessions[session_id] = session.model_copy(
                            update={"active_pending_process_id": None, "updated_at": utc_now()},
                            deep=True,
                        )
                for process_id in expired:
                    for session_ids in self._pending_session_ids.values():
                        session_ids.discard(process_id)

        return expired_ids

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
            ),
            None,
        )
        pending_context = (
            self._pending_contexts.get(session.active_pending_process_id)
            if session.active_pending_process_id
            else None
        )
        return ConversationSessionSummary(
            session_id=session.session_id,
            channel=session.channel,
            external_conversation_id=session.external_conversation_id,
            owner_id=session.owner_id,
            title=session.title,
            status=session.status,
            active_pending_process_id=session.active_pending_process_id,
            pending_process_status=(
                pending_context.process_ref.status if pending_context else None
            ),
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


def _can_autotitle(session: ConversationSession) -> bool:
    return (
        session.title == "New chat"
        and str(session.metadata.get("title_source") or "default") != "manual"
    )
