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
    PlanningPurposeGuidelines,
    PlanningTransformContext,
)
from my_digital_brain.agentic.contexts import PlanningContext, SourceContext
from my_digital_brain.agentic.runtime_models import AgenticStateRunResult
from my_digital_brain.ai.schemas import ChatMessage
from my_digital_brain.clarification.interaction import build_clarification_packet
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


def test_history_service_promotes_selected_messages_to_master_history() -> None:
    service = AgenticHistoryService()

    history = service.promote_messages_to_master_history(
        [{"role": "user", "content": "Store this memory."}],
        [
            ChatMessage(role="assistant", content="Who's Amos?"),
            ChatMessage(role="user", content="Amos Vignaroli"),
        ],
    )

    assert history == [
        {"role": "user", "content": "Store this memory."},
        {"role": "assistant", "content": "Who's Amos?"},
        {"role": "user", "content": "Amos Vignaroli"},
    ]


def test_history_service_promotes_clarification_question_without_options() -> None:
    service = AgenticHistoryService()
    packet = build_clarification_packet(
        frame_id="frame-1",
        origin_state_id="node",
        reason="The name is ambiguous.",
        questions=[
            {
                "question": "Who is Amos?",
                "options": [{"label": "Amos Vignaroli"}],
            }
        ],
    )

    history = service.promote_clarification_to_master_history(
        [{"role": "user", "content": "Store this memory."}],
        packet,
        answer_messages=[{"role": "user", "content": "Amos Vignaroli"}],
    )

    assert history == [
        {"role": "user", "content": "Store this memory."},
        {"role": "assistant", "content": "Who is Amos?"},
        {"role": "user", "content": "Amos Vignaroli"},
    ]


def test_history_service_appends_source_once_to_master_history() -> None:
    service = AgenticHistoryService()

    history = service.append_user_message_to_master_history(
        [{"role": "user", "content": "Earlier message."}],
        "Store this memory.",
    )
    history = service.append_user_message_to_master_history(history, "Store this memory.")

    assert history == [
        {"role": "user", "content": "Earlier message."},
        {"role": "user", "content": "Store this memory."},
    ]


def test_history_service_renders_role_preserved_messages_and_tool_outputs() -> None:
    service = AgenticHistoryService()
    tool_call = NeutralConversationMessage.assistant_tool_call(
        "query_memory",
        {"question": "What about Marco?"},
    )
    tool_output = NeutralConversationMessage.tool_output_message(
        tool_call_id=tool_call.tool_call.tool_call_id,
        name="query_memory",
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
    assert messages[1].tool_calls[0]["function"]["name"] == "query_memory"
    assert messages[2].tool_call_id == tool_call.tool_call.tool_call_id
    assert messages[-1].content == "And Alessia?"
    assert "history" not in prompt_context
    assert "current_message" not in prompt_context
    assert "channel_metadata" not in prompt_context


def test_history_service_appends_model_user_message_after_source_text() -> None:
    service = AgenticHistoryService()
    context = PlanningTransformContext(
        purpose=PlanningPurposeGuidelines(goal="Extract a memory log."),
        input_context={
            "source_text": "Merc came to the barbeque.",
            "model_user_message": "Ingest MEMORY_LOG_001.",
        },
    )

    messages = service.model_messages_for_state(
        AgenticStateId.MEMORY_LOG_EXTRACTION,
        context,
    )
    prompt_context = service.model_prompt_context_for_state(
        AgenticStateId.MEMORY_LOG_EXTRACTION,
        context,
    )

    assert [message.role for message in messages] == ["user", "user"]
    assert messages[0].content == "Merc came to the barbeque."
    assert messages[1].content == "Ingest MEMORY_LOG_001."
    assert "source_text" not in str(prompt_context)
    assert "model_user_message" not in str(prompt_context)


def test_history_service_appends_transient_message_without_mutating_conversation() -> None:
    service = AgenticHistoryService()
    conversation = ConversationContext(
        current_message=NeutralConversationMessage.user("Original user message."),
        history=[NeutralConversationMessage.assistant("Previous answer.")],
    )
    context = PlanningTransformContext(
        purpose=PlanningPurposeGuidelines(goal="Extract a memory log."),
        input_context={"model_user_message": "Ingest MEMORY_LOG_001."},
        conversation=conversation,
    )

    messages = service.model_messages_for_state(
        AgenticStateId.MEMORY_LOG_EXTRACTION,
        context,
    )

    assert [message.content for message in messages] == [
        "Previous answer.",
        "Original user message.",
        "Ingest MEMORY_LOG_001.",
    ]
    assert conversation.current_message.content == "Original user message."
    assert [message.content for message in conversation.history] == ["Previous answer."]


def test_history_service_compacts_tool_events_for_planning_checkpoint_context() -> None:
    service = AgenticHistoryService(HistoryProjectionPolicy(tool_data_chars=80))
    planning_context = PlanningContext(
        source=SourceContext(source_id="source-1", normalized_text="I met Marco."),
        conversation=ConversationContext(
            current_message=NeutralConversationMessage.user("I met Marco."),
        ),
    )
    state_result = AgenticStateRunResult(
        state_id=AgenticStateId.PLANNING_CHECKPOINT,
        tool_events=[
            AgenticToolEvent(
                tool_name="get_context_package",
                status="ok",
                output="Graph context expanded.",
                data={"matches": [{"text": "x" * 200}]},
            ),
            AgenticToolEvent(
                tool_name="ask_clarification",
                status="ok",
                data={"clarification_packet": {"question": "Which Marco?"}},
            ),
        ],
    )

    service.append_tool_events_to_planning_context(
        planning_context,
        state_result,
    )

    assert len(planning_context.prior_tool_outputs) == 2
    output = planning_context.prior_tool_outputs[0]
    assert output.tool_name == "get_context_package"
    assert output.summary == "Graph context expanded."
    assert output.data["truncated"] is True
    assert planning_context.prior_tool_outputs[1].tool_name == "ask_clarification"


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
