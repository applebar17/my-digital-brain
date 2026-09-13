from __future__ import annotations

from datetime import UTC, datetime

from my_digital_brain.agentic.enums import AgenticStateId
from my_digital_brain.chat.activity import (
    activity_presentation,
    activity_title,
    known_activity_keys,
)
from my_digital_brain.chat.enums import ChatActivityStatus, ChatProcessStatus
from my_digital_brain.chat.models import ChatActivityEvent, ChatProcessSnapshot
from my_digital_brain.chat.store import InMemoryChatSessionStore


def test_activity_registry_covers_current_agentic_states() -> None:
    keys = set(known_activity_keys())

    assert {state.value for state in AgenticStateId} <= keys


def test_activity_title_is_stable_and_cycles_variants() -> None:
    key = AgenticStateId.REASONING_CHECKPOINT.value

    assert activity_title(key, occurrence=0) == activity_title(key, occurrence=0)
    assert activity_title(key, occurrence=3) == activity_title(key, occurrence=0)
    assert len({activity_title(key, occurrence=index) for index in range(3)}) == 3


def test_unknown_activity_uses_safe_user_facing_fallback() -> None:
    presentation = activity_presentation("future_state")

    assert presentation.activity_group == "understanding"
    assert "future_state" not in presentation.summary
    assert "future_state" not in activity_title("future_state")


def test_activity_contract_contains_no_internal_source_identifier() -> None:
    event = ChatActivityEvent(
        sequence=1,
        status=ChatActivityStatus.STARTED,
        title="Searching your memories",
        summary="Checking related memories and existing context.",
        activity_group="memory",
    )
    snapshot = ChatProcessSnapshot(
        status=ChatProcessStatus.WORKING,
        current_activity=event,
        recent_activities=[event],
        started_at=datetime.now(UTC),
    )

    payload = snapshot.model_dump(mode="json")

    assert "state_id" not in payload
    assert "frame_id" not in payload
    assert payload["current_activity"]["title"] == "Searching your memories"


def test_in_memory_store_keeps_current_activity_separate_from_recent_history() -> None:
    store = InMemoryChatSessionStore()
    session = store.create_session(channel="web", owner_id="owner")

    started = store.begin_chat_process(session.session_id)
    assert started.status == ChatProcessStatus.WORKING

    store.publish_chat_activity(
        session.session_id,
        AgenticStateId.REASONING_CHECKPOINT.value,
        ChatActivityStatus.STARTED,
    )
    current = store.get_chat_process_snapshot(session.session_id)
    assert current.current_activity is not None
    assert current.current_activity.activity_group == "understanding"
    assert current.recent_activities == []

    store.publish_chat_activity(
        session.session_id,
        AgenticStateId.REASONING_CHECKPOINT.value,
        ChatActivityStatus.COMPLETED,
    )
    completed = store.get_chat_process_snapshot(session.session_id)
    assert completed.current_activity is None
    assert len(completed.recent_activities) == 1
    assert completed.recent_activities[0].status == ChatActivityStatus.COMPLETED
