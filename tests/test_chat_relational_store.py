from __future__ import annotations

from sqlalchemy import create_engine

from my_digital_brain.chat.enums import (
    ChatChannel,
    ConversationMessageRole,
    ConversationStatus,
)
from my_digital_brain.chat.models import ConversationMessage
from my_digital_brain.chat.relational_store import RelationalChatSessionStore
from my_digital_brain.storage.relational import RelationalSessionProvider
from my_digital_brain.storage.relational_models import Base


def test_relational_chat_store_persists_sessions_messages_and_recent_summaries(tmp_path) -> None:
    store = _store(tmp_path)

    first = store.create_session(channel=ChatChannel.WEB, owner_id="owner-1")
    second = store.create_session(
        channel=ChatChannel.WEB,
        owner_id="owner-1",
        title="Manual title",
    )
    store.append_message(
        ConversationMessage(
            session_id=first.session_id,
            role=ConversationMessageRole.USER,
            text="Yesterday I met Marco in Milan.",
        ),
    )
    store.append_message(
        ConversationMessage(
            session_id=second.session_id,
            role=ConversationMessageRole.USER,
            text="This should not leak into the first chat.",
        ),
    )

    first_detail = store.get_session_detail(first.session_id)
    summaries = store.list_sessions(owner_id="owner-1", channel=ChatChannel.WEB)

    assert first_detail.session.title == "Yesterday I met Marco in Milan."
    assert [message.text for message in first_detail.messages] == [
        "Yesterday I met Marco in Milan.",
    ]
    assert {summary.session_id for summary in summaries} == {first.session_id, second.session_id}
    assert all(summary.owner_id == "owner-1" for summary in summaries)


def test_relational_chat_store_renames_archives_and_hides_archived_by_default(tmp_path) -> None:
    store = _store(tmp_path)
    session = store.create_session(channel=ChatChannel.WEB, owner_id="owner-1")

    renamed = store.rename_session(session.session_id, "Renamed chat")
    archived = store.archive_session(session.session_id)

    assert renamed.title == "Renamed chat"
    assert archived.status == ConversationStatus.ARCHIVED
    assert store.list_sessions(owner_id="owner-1") == []
    assert store.list_sessions(owner_id="owner-1", include_archived=True)[0].session_id == session.session_id



def test_relational_chat_store_has_no_pending_process_api(tmp_path) -> None:
    store = _store(tmp_path)

    assert not hasattr(store, "save_pending_process_context")
    assert not hasattr(store, "get_active_pending_process_context")
    assert not hasattr(store, "list_pending_process_contexts")


def _store(tmp_path) -> RelationalChatSessionStore:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'chat.sqlite3').as_posix()}", future=True)
    Base.metadata.create_all(engine)
    return RelationalChatSessionStore(RelationalSessionProvider(engine))
