from __future__ import annotations

from datetime import UTC, datetime

from my_digital_brain.agentic import (
    AgenticHistoryService,
    AgenticStateId,
    AgenticToolEvent,
    ChannelSessionMetadata,
    ConversationContext,
    HistoryProjectionPolicy,
    NeutralConversationMessage,
)
from my_digital_brain.agentic.contexts import PlanningContext, SourceContext
from my_digital_brain.agentic.runtime_models import AgenticStateRunResult
from my_digital_brain.chat.enums import ConversationMessageRole
from my_digital_brain.chat.models import ConversationMessage


def test_history_service_builds_internal_conversation_and_prompt_safe_payload() -> None:
    service = AgenticHistoryService(HistoryProjectionPolicy(max_history_messages=2))
    messages = [
        _message("m1", ConversationMessageRole.USER, "First memory."),
        _message("m2", ConversationMessageRole.ASSISTANT, "Stored."),
        _message("m3", ConversationMessageRole.USER, "Second memory."),
        _message("m4", ConversationMessageRole.USER, "Current message."),
    ]

    context = service.build_conversation_context(
        current_text="Current message.",
        history_records=messages,
        current_time=datetime(2026, 6, 2, tzinfo=UTC),
        timezone="Europe/Rome",
        channel_metadata=ChannelSessionMetadata(
            channel="web",
            conversation_id="conversation-1",
            owner_id="owner-1",
            session_id="session-1",
        ),
        exclude_record_ids={"m4"},
    )
    payload = service.model_payload_for_state(AgenticStateId.CONVERSATION_ENTRY, context)

    assert context.channel_metadata is not None
    assert context.compacted_summary.startswith("Earlier conversation summary:")
    assert [message.content for message in context.history] == ["Stored.", "Second memory."]
    assert "channel_metadata" not in payload
    assert payload["timezone"] == "Europe/Rome"
    assert payload["compacted_summary"].startswith("Earlier conversation summary:")


def test_history_service_child_projection_removes_channel_metadata() -> None:
    service = AgenticHistoryService()
    conversation = ConversationContext(
        current_message=NeutralConversationMessage.user("What about Marco?"),
        history=[NeutralConversationMessage.assistant("Marco is a friend.")],
        channel_metadata=ChannelSessionMetadata(
            channel="telegram",
            conversation_id="chat-1",
            owner_id="owner-1",
        ),
    )

    child = service.child_conversation_context(conversation)
    payload = service.model_payload_for_state(AgenticStateId.MEMORY_QUERY, child)

    assert child.channel_metadata is None
    assert "channel_metadata" not in payload
    assert payload["history"][0]["content"] == "Marco is a friend."


def test_history_service_renders_role_preserved_messages_and_tool_outputs() -> None:
    service = AgenticHistoryService()
    tool_call = NeutralConversationMessage.assistant_tool_call(
        "query_memory_context",
        {"question": "What about Marco?"},
    )
    tool_output = NeutralConversationMessage.tool_output_message(
        tool_call_id=tool_call.tool_call.tool_call_id,
        name="query_memory_context",
        content='{"status":"ok"}',
    )
    conversation = ConversationContext(
        current_message=NeutralConversationMessage.user("And Alessia?"),
        history=[
            NeutralConversationMessage.user("What about Marco?"),
            tool_call,
            tool_output,
            NeutralConversationMessage.assistant("Marco is a university friend."),
        ],
        channel_metadata=ChannelSessionMetadata(
            channel="web",
            conversation_id="conversation-1",
            owner_id="owner-1",
        ),
        compacted_summary="Older memory discussion.",
    )

    messages = service.model_messages_for_state(
        AgenticStateId.CONVERSATION_ENTRY,
        conversation,
    )
    prompt_context = service.model_prompt_context_for_state(
        AgenticStateId.CONVERSATION_ENTRY,
        conversation,
    )

    assert [message.role for message in messages] == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "user",
    ]
    assert messages[1].tool_calls[0]["function"]["name"] == "query_memory_context"
    assert messages[2].tool_call_id == tool_call.tool_call.tool_call_id
    assert messages[-1].content == "And Alessia?"
    assert "history" not in prompt_context
    assert "current_message" not in prompt_context
    assert "channel_metadata" not in prompt_context


def test_history_service_compacts_tool_events_for_planning_context() -> None:
    service = AgenticHistoryService(HistoryProjectionPolicy(tool_data_chars=80))
    planning_context = PlanningContext(
        source=SourceContext(source_id="source-1", normalized_text="I met Marco."),
        conversation=ConversationContext(
            current_message=NeutralConversationMessage.user("I met Marco."),
        ),
    )
    state_result = AgenticStateRunResult(
        state_id=AgenticStateId.MEMORY_INGESTION_PLANNING,
        tool_events=[
            AgenticToolEvent(
                tool_name="request_graph_context_expansion",
                status="ok",
                output="Graph context expanded.",
                data={"matches": [{"text": "x" * 200}]},
            ),
            AgenticToolEvent(
                tool_name="request_contradiction_review",
                status="ok",
                data={"handoff_target": "contradiction_review"},
            ),
        ],
    )

    service.append_tool_events_to_planning_context(
        planning_context,
        state_result,
        skip_handoff_targets={"contradiction_review"},
    )

    assert len(planning_context.prior_tool_outputs) == 1
    output = planning_context.prior_tool_outputs[0]
    assert output.tool_name == "request_graph_context_expansion"
    assert output.summary == "Graph context expanded."
    assert output.data["truncated"] is True


def _message(
    channel_message_id: str,
    role: ConversationMessageRole,
    text: str,
) -> ConversationMessage:
    return ConversationMessage(
        session_id="session-1",
        channel_message_id=channel_message_id,
        role=role,
        text=text,
    )
