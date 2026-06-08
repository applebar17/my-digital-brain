from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from my_digital_brain.agentic import (
    AgenticStateId,
    ChannelContextProjection,
    ChannelSessionMetadata,
    ConversationContext,
    DeterministicAgenticRouter,
    NeutralConversationMessage,
    PendingMessageIntent,
    PendingProcessContext,
    PlanningActionContext,
    PlanningPurposeGuidelines,
    PlanningTransformContext,
    PlanningTransformResultContext,
    ResponseRenderStyle,
    ToolResultStatus,
    default_state_configs,
)
from my_digital_brain.prompts import PromptNotFoundError, PromptRegistry


def test_neutral_conversation_messages_validate_expected_shapes() -> None:
    user = NeutralConversationMessage.user("Yesterday I met Marco.")
    call = NeutralConversationMessage.assistant_tool_call(
        "start_memory_ingestion",
        {"source_text": "Yesterday I met Marco."},
    )
    output = NeutralConversationMessage.tool_output_message(
        tool_call_id=call.tool_call.tool_call_id,
        name="start_memory_ingestion",
        status=ToolResultStatus.ACCEPTED,
        content="Memory accepted.",
    )
    summary = NeutralConversationMessage.compacted_summary(
        "Older discussion: Marco from university was mentioned."
    )

    assert user.content == "Yesterday I met Marco."
    assert call.tool_call.name == "start_memory_ingestion"
    assert output.tool_output.status == ToolResultStatus.ACCEPTED.value
    assert summary.content.startswith("Older discussion")

    with pytest.raises(ValidationError):
        NeutralConversationMessage(kind="assistant_tool_call", content="missing tool call")


def test_conversation_context_excludes_backend_channel_metadata_from_model_payload() -> None:
    context = ConversationContext(
        current_message=NeutralConversationMessage.user("hello"),
        history=[
            NeutralConversationMessage.user("hello"),
            NeutralConversationMessage.assistant("hi"),
        ],
        timezone="Europe/Rome",
        channel_metadata=ChannelSessionMetadata(
            channel="telegram",
            conversation_id="telegram-chat-1",
            owner_id="owner-1",
            sender_id="sender-1",
            metadata={"raw_chat_id": "private"},
        ),
        channel_projection=ChannelContextProjection(
            render_style=ResponseRenderStyle.SHORT_CHAT,
            timezone="Europe/Rome",
        ),
    )

    payload = context.model_facing_payload()

    assert "channel_metadata" not in payload
    assert payload["channel_projection"]["render_style"] == "short_chat"
    assert payload["timezone"] == "Europe/Rome"


def test_generic_planning_contracts_accept_caller_context_and_schema() -> None:
    purpose = PlanningPurposeGuidelines(
        purpose_id="entity_planning",
        goal="Plan lightweight entity extraction from source text.",
        focus_areas=["entities", "aliases"],
        instructions=["Keep metadata out of the plan."],
        output_usage="EntityIngestionPlanDraft",
        forbidden_assumptions=["Do not treat aliases as identity."],
    )
    context = PlanningTransformContext(
        purpose=purpose,
        input_context={"source_text": "Merc is Matteo Mercoldi.", "graph_view": []},
        reasoning_artifact={"summary": "Merc may be an alias for Matteo Mercoldi."},
        timezone="Europe/Rome",
        expected_output_schema={"title": "EntityIngestionPlanDraft"},
    )
    result = PlanningTransformResultContext(
        planning_id=context.planning_id,
        purpose_id=purpose.purpose_id,
        summary="Plan one entity action.",
        actions=[
            PlanningActionContext(
                action_ref="ACTION_001",
                goal="Extract Matteo Mercoldi as a person candidate.",
                action_kind="extract_entity",
                target_refs=["source_text"],
                evidence_text="Merc is Matteo Mercoldi.",
            ),
        ],
    )

    assert context.input_context["source_text"] == "Merc is Matteo Mercoldi."
    assert context.expected_output_schema == {"title": "EntityIngestionPlanDraft"}
    assert result.actions[0].action_ref == "ACTION_001"

    with pytest.raises(ValidationError, match="summary"):
        PlanningTransformResultContext(
            planning_id=context.planning_id,
            purpose_id=purpose.purpose_id,
            summary=" ",
            context_gaps=["missing source text"],
        )
    with pytest.raises(ValidationError, match="useful signal"):
        PlanningTransformResultContext(
            planning_id=context.planning_id,
            purpose_id=purpose.purpose_id,
            summary="No useful payload.",
        )


def test_default_state_configs_lock_wave1_toolboxes() -> None:
    configs = default_state_configs()

    entry = configs[AgenticStateId.CONVERSATION_ENTRY]
    pending = configs[AgenticStateId.PENDING_PROCESS_REVIEW]
    reasoning = configs[AgenticStateId.REASONING_CHECKPOINT]

    assert entry.prompt_id == "conversation_entry"
    assert entry.allowed_tools == [
        "start_memory_ingestion",
        "query_memory_context",
        "propose_memory_correction",
    ]
    assert "cancel_pending_process" not in entry.allowed_tools
    assert "get_conversation_status" not in entry.allowed_tools
    assert "focused_extraction" in entry.forbidden_tools
    assert "pause_pending_process" in pending.allowed_tools
    assert "cancel_pending_process" in pending.allowed_tools
    assert pending.required_context_type == "ConversationContext"
    assert reasoning.prompt_id == "reasoning_checkpoint"
    assert reasoning.required_context_type == "ReasoningCheckpointContext"
    assert reasoning.produced_context_type == "ReasoningCheckpointResultContext"
    assert "get_context_package" in reasoning.allowed_tools
    assert "request_user_clarification" in reasoning.allowed_tools
    assert "execute_graph_write_plan" in reasoning.forbidden_tools
    planning = configs[AgenticStateId.PLANNING_CHECKPOINT]
    assert planning.prompt_id == "planning_checkpoint"
    assert planning.required_context_type == "PlanningTransformContext"
    assert planning.produced_context_type == "PlanningTransformResultContext"
    assert "get_context_package" in planning.allowed_tools
    assert "request_user_clarification" in planning.allowed_tools
    assert "focused_extraction" in planning.forbidden_tools


def test_prompt_registry_loads_default_templates_and_renders_variables(tmp_path: Path) -> None:
    default_registry = PromptRegistry()
    prompt = default_registry.load("conversation_entry")

    assert prompt.prompt_id == "conversation_entry"
    assert "top-level tools" in prompt.template
    assert "structured output schema" in default_registry.load(
        "reasoning_checkpoint",
    ).template
    assert "reusable planning checkpoint" in default_registry.load(
        "planning_checkpoint",
    ).template

    prompt_dir = tmp_path / "example"
    prompt_dir.mkdir()
    (prompt_dir / "v1.system.md").write_text("Hello {{ name }}.", encoding="utf-8")
    registry = PromptRegistry(root=tmp_path)

    assert registry.render("example", variables={"name": "Marco"}) == "Hello Marco."
    with pytest.raises(ValueError, match="Missing prompt variables"):
        registry.render("example")
    with pytest.raises(PromptNotFoundError):
        registry.load("missing")


def test_deterministic_router_does_not_infer_default_memory_action() -> None:
    router = DeterministicAgenticRouter()
    context = ConversationContext(
        current_message=NeutralConversationMessage.user("Yesterday I met Marco."),
    )

    route = router.route(context)

    assert route.entry_state == AgenticStateId.CONVERSATION_ENTRY.value
    assert route.tool_call is None
    assert route.assistant_message is not None
    assert "Provider-backed conversation routing" in route.assistant_message.content


def test_deterministic_router_does_not_expose_control_tools_to_conversation_entry() -> None:
    router = DeterministicAgenticRouter()
    status_context = ConversationContext(
        current_message=NeutralConversationMessage.user("/status"),
    )
    cancel_context = ConversationContext(
        current_message=NeutralConversationMessage.user("skip"),
    )

    status_route = router.route(status_context)
    cancel_route = router.route(cancel_context)

    assert status_route.entry_state == AgenticStateId.CONVERSATION_ENTRY.value
    assert status_route.tool_call is None
    assert status_route.assistant_message is not None
    assert "control layer" in status_route.assistant_message.content
    assert cancel_route.tool_call is None
    assert cancel_route.assistant_message is not None
    assert "no active pending process" in cancel_route.assistant_message.content


def test_deterministic_router_uses_pending_review_and_can_pause() -> None:
    router = DeterministicAgenticRouter()
    context = ConversationContext(
        current_message=NeutralConversationMessage.user("I don't remember"),
        pending_process=PendingProcessContext(
            process_id="process-1",
            kind="memory_ingestion",
            status="pending",
            question="Which place was it?",
        ),
    )

    route = router.route(context)

    assert route.entry_state == AgenticStateId.PENDING_PROCESS_REVIEW.value
    assert route.pending_intent == PendingMessageIntent.PAUSE.value
    assert route.tool_call.name == "pause_pending_process"
    assert route.tool_call.arguments["pending_process_id"] == "process-1"


def test_deterministic_router_does_not_infer_pending_resume_by_default() -> None:
    router = DeterministicAgenticRouter()
    context = ConversationContext(
        current_message=NeutralConversationMessage.user("Marco from university"),
        pending_process=PendingProcessContext(
            process_id="process-1",
            kind="memory_ingestion",
            status="pending",
            question="Which Marco?",
        ),
    )

    route = router.route(context)

    assert route.entry_state == AgenticStateId.PENDING_PROCESS_REVIEW.value
    assert route.pending_intent is None
    assert route.tool_call is None
    assert route.assistant_message is not None
    assert "Provider-backed pending process review" in route.assistant_message.content
