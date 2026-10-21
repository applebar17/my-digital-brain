from copy import deepcopy

import pytest
from pydantic import BaseModel

from product.agentic.contracts import PausedStateContinuationDTO
from product.agentic.history import AgenticHistorySession
from product.ai.ai_clients.protocols.protocol_chat import Msg, TextPart


def test_root_and_child_runs_have_separate_msg_transcripts_and_parent_linkage() -> None:
    projection = [
        Msg(role="user", content="Remember this.", meta={"source": {"id": "m1"}}),
        Msg(role="assistant", content=[TextPart(text="I will.")]),
    ]
    original_projection = deepcopy(projection)
    session = AgenticHistorySession(projection)

    root = session.start_state("conversation_entry", projection)
    child_projection = session.master_history[:1]
    child = session.start_state(
        "memory_query",
        child_projection,
        parent_state_run_id=root.state_run_id,
        parent_provider_call_id="call_query_1",
    )

    assert root.state_run_id != child.state_run_id
    assert child.parent_state_run_id == root.state_run_id
    assert child.parent_provider_call_id == "call_query_1"
    assert child.master_history_revision == root.master_history_revision == 0

    child.messages[0].meta["source"]["id"] = "changed-in-child"
    child.messages.append(Msg(role="assistant", content="Child-only response."))
    assert root.messages == original_projection
    assert projection == original_projection


def test_master_promotion_is_explicit_copied_and_records_origin_revision() -> None:
    initial = [Msg(role="user", content="Original message.")]
    promoted = Msg(role="assistant", content="Selected summary.", meta={"source": ["s1"]})
    session = AgenticHistorySession(initial)
    state = session.start_state("memory_query", session.master_history)

    assert session.promote_to_master(state.state_run_id, []) == 0
    assert session.master_history == initial

    assert session.promote_to_master(state.state_run_id, [promoted]) == 1
    promoted.meta["source"].append("mutated-outside")

    assert session.master_revision == 1
    assert session.master_history == [
        *initial,
        Msg(role="assistant", content="Selected summary.", meta={"source": ["s1"]}),
    ]
    assert session.promotions[0].origin_state_run_id == state.state_run_id
    assert session.promotions[0].revision == 1
    assert session.promotions[0].message_count == 1


def test_completed_state_is_released_without_mutating_its_parent() -> None:
    session = AgenticHistorySession()
    root = session.start_state("root", [])
    child = session.start_state("child", [], parent_state_run_id=root.state_run_id)

    session.complete_state(child.state_run_id)

    assert session.get_state(root.state_run_id) is root
    with pytest.raises(ValueError, match="is not active"):
        session.get_state(child.state_run_id)
    with pytest.raises(ValueError, match="is not active"):
        session.complete_state(child.state_run_id)


def test_child_run_requires_an_active_parent_and_parent_call_linkage() -> None:
    session = AgenticHistorySession()

    with pytest.raises(ValueError, match="is not active"):
        session.start_state("child", [], parent_state_run_id="missing-parent")
    with pytest.raises(ValueError, match="requires a parent state run ID"):
        session.start_state("root", [], parent_provider_call_id="call-without-parent")


def test_pause_preserves_transcript_and_resume_restores_same_state_run() -> None:
    class QuestionPacket(BaseModel):
        question: str

    open_tool_turn = Msg(
        role="assistant",
        content=None,
        meta={
            "tool_calls": [
                {"id": "call-question", "name": "ask_user", "arguments": "{}"}
            ]
        },
    )
    session = AgenticHistorySession()
    state = session.start_state("clarification_child", [open_tool_turn])

    continuation = session.pause_state(
        state.state_run_id,
        "call-question",
        QuestionPacket(question="Which person do you mean?"),
    )

    assert isinstance(continuation, PausedStateContinuationDTO[QuestionPacket])
    assert continuation.interaction_packet.question == "Which person do you mean?"
    assert continuation.state_history.state_run_id == state.state_run_id
    assert continuation.state_history.messages == [open_tool_turn]
    assert not any(message.role == "tool" for message in state.messages)

    restored_continuation = PausedStateContinuationDTO[QuestionPacket].model_validate_json(
        continuation.model_dump_json()
    )
    assert isinstance(restored_continuation.interaction_packet, QuestionPacket)
    assert (
        restored_continuation.state_history.messages[0].meta["tool_calls"][0]["id"]
        == "call-question"
    )

    state.messages.append(Msg(role="assistant", content="must be discarded on restore"))
    resumed = session.resume_state(restored_continuation)

    assert resumed is state
    assert resumed.state_run_id == continuation.state_history.state_run_id
    assert resumed.messages == [open_tool_turn]
    assert not any(message.role == "tool" for message in resumed.messages)


def test_pause_and_resume_reject_invalid_lifecycle_transitions() -> None:
    class QuestionPacket(BaseModel):
        question: str

    session = AgenticHistorySession()
    state = session.start_state("clarification_child", [])
    packet = QuestionPacket(question="Who?")

    with pytest.raises(ValueError, match="is not active"):
        session.pause_state("missing-run", "call-1", packet)

    continuation = session.pause_state(state.state_run_id, "call-1", packet)
    with pytest.raises(ValueError, match="already paused"):
        session.pause_state(state.state_run_id, "call-2", packet)

    session.resume_state(continuation)
    with pytest.raises(ValueError, match="is not paused"):
        session.resume_state(continuation)
