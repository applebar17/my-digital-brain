from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from my_digital_brain.ai.models import ToolResult as ProviderToolResult
from my_digital_brain.agentic import (
    AgenticStateId,
    ChannelContextProjection,
    ChannelSessionMetadata,
    ConversationContext,
    DeterministicAgenticRouter,
    MemoryCreationContext,
    AgenticToolPayload,
    MemoryPlan,
    MemoryPlanAction,
    MemoryPlanActionType,
    NeutralConversationMessage,
    PendingProcessContext,
    PlanningActionContext,
    PlanningPurposeGuidelines,
    PlanningTransformContext,
    PacketDetailProfile,
    PlanningTransformResultContext,
    RefContext,
    RefEntry,
    RefObjectKind,
    RefResolutionStatus,
    ResponseRenderStyle,
    ToolResultStatus,
    build_ref_packet,
    default_state_configs,
)
from my_digital_brain.graph.models import NodeSearchResult, RelationshipResult
from my_digital_brain.prompts import PromptNotFoundError, PromptRegistry


def test_neutral_conversation_messages_validate_expected_shapes() -> None:
    user = NeutralConversationMessage.user("Yesterday I met Marco.")
    call = NeutralConversationMessage.assistant_tool_call(
        "ingest_memory",
        {},
    )
    output = NeutralConversationMessage.tool_output_message(
        tool_call_id=call.tool_call.tool_call_id,
        name="ingest_memory",
        status=ToolResultStatus.ACCEPTED,
        content="Memory accepted.",
    )
    summary = NeutralConversationMessage.compacted_summary(
        "Older discussion: Marco from university was mentioned."
    )

    assert user.content == "Yesterday I met Marco."
    assert call.tool_call.name == "ingest_memory"
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


def test_memory_plan_and_creation_contracts_lock_wave1_shape() -> None:
    conversation = ConversationContext(
        current_message=NeutralConversationMessage.user("Remember I met Marco yesterday."),
    )
    action = MemoryPlanAction(
        action_id="ACTION_001",
        action_type=MemoryPlanActionType.CREATE_MEMORY_LOG,
        target_refs=["NODE_000001"],
        payload={"log_kind": "memory"},
    )
    plan = MemoryPlan(context_refs=["PACKAGE_001"], actions=[action])
    creation = MemoryCreationContext(conversation=conversation, action=action)

    assert str(MemoryPlanActionType.CREATE_MEMORY_LOG) == "create_memory_log"
    assert plan.actions[0].action_type == MemoryPlanActionType.CREATE_MEMORY_LOG
    assert creation.action.action_id == "ACTION_001"
    assert "source_text" not in MemoryCreationContext.model_fields
    assert "source_text" not in creation.model_facing_payload()

    with pytest.raises(ValidationError, match="at least one action"):
        MemoryPlan(actions=[])
    with pytest.raises(ValidationError):
        MemoryPlanAction(action_type="delete_node")


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
    assert "planning_id" not in context.model_facing_payload()
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
    reasoning = configs[AgenticStateId.REASONING_CHECKPOINT]

    assert "pending_process_review" not in {state.value for state in configs}
    assert entry.prompt_id == "conversation_entry"
    assert entry.allowed_tools == [
        "query_memory",
        "ingest_memory",
    ]
    assert configs[AgenticStateId.MEMORY_INGESTION].required_context_type == (
        "MemoryIngestionContext"
    )
    assert configs[AgenticStateId.MEMORY_CREATION].required_context_type == (
        "MemoryCreationContext"
    )
    assert "run_memory_creation" in configs[AgenticStateId.MEMORY_INGESTION].allowed_tools
    assert "request_user_clarification" not in configs[AgenticStateId.MEMORY_QUERY].allowed_tools
    assert "cancel_pending_process" not in entry.allowed_tools
    assert "get_conversation_status" not in entry.allowed_tools
    assert "focused_extraction" in entry.forbidden_tools
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
    assert "memory ingestion state" in default_registry.load("memory_ingestion").template
    assert "memory creation state" in default_registry.load("memory_creation").template

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
    assert "tool surface" in status_route.assistant_message.content
    assert cancel_route.tool_call is None
    assert cancel_route.assistant_message is not None
    assert "Pending-process cancellation" in cancel_route.assistant_message.content


def test_deterministic_router_keeps_pending_context_in_conversation_entry() -> None:
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

    assert route.entry_state == AgenticStateId.CONVERSATION_ENTRY.value
    assert route.tool_call is None
    assert route.assistant_message is not None
    assert "Provider-backed conversation routing" in route.assistant_message.content


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

    assert route.entry_state == AgenticStateId.CONVERSATION_ENTRY.value
    assert route.tool_call is None
    assert route.assistant_message is not None
    assert "Provider-backed conversation routing" in route.assistant_message.content



def test_ref_context_contracts_allocate_and_hide_backend_ids() -> None:
    context = RefContext(session_id="ingestion-1")
    first = context.add_hydrated(
        RefObjectKind.NODE,
        backend_id="node-backend-1",
        label="Person",
        name="Marco Bianchi",
        aliases=["Marco"],
    )
    second = context.add_hydrated("node", backend_id="node-backend-2", label="Place", name="Rome")
    proposed = context.add_proposed("node", label="Person", name="Lorenzo Tordini")

    assert first.ref == "node_0001"
    assert second.ref == "node_0002"
    assert proposed.ref == "node_new_0001"
    assert context.backend_id_for_ref("node_0001") == "node-backend-1"

    packet = context.model_facing_packet(PacketDetailProfile.MEDIUM)
    assert packet[0]["ref"] == "node_0001"
    assert packet[0]["name"] == "Marco Bianchi"
    assert packet[0]["aliases"] == ["Marco"]
    assert "backend_id" not in packet[0]

    independent = RefContext(session_id="ingestion-2")
    assert independent.add_hydrated("node", backend_id="other-node").ref == "node_0001"


def test_ref_context_rejects_malformed_colliding_and_wrong_kind_refs() -> None:
    context = RefContext()
    context.add_entry(
        RefEntry(ref="node_0001", object_kind=RefObjectKind.NODE, backend_id="node-1"),
    )

    with pytest.raises(ValueError, match="already exists"):
        context.add_entry(RefEntry(ref="node_0001", object_kind=RefObjectKind.NODE))
    with pytest.raises(ValidationError):
        RefEntry(ref="NODE_0001", object_kind=RefObjectKind.NODE)
    with pytest.raises(ValidationError):
        RefEntry(ref="node_0001", object_kind=RefObjectKind.MEMORY)
    with pytest.raises(ValueError, match="Unknown ref"):
        context.get_entry("node_9999")

    resolved = context.resolve_backend_id("node_0001", "node-1", status=RefResolutionStatus.CREATED)
    assert resolved.ref == "node_0001"
    assert resolved.backend_id == "node-1"
    assert resolved.resolution_status == RefResolutionStatus.CREATED.value


def test_packet_profiles_include_expected_field_sets() -> None:
    entry = RefEntry(
        ref="node_0001",
        object_kind=RefObjectKind.NODE,
        label="Person",
        name="Marco Bianchi",
        summary="Known friend from university.",
        aliases=["Marco"],
        backend_id="node-1",
    )

    short = entry.model_facing_packet(PacketDetailProfile.SHORT)
    medium = entry.model_facing_packet(PacketDetailProfile.MEDIUM)
    long = entry.model_facing_packet(PacketDetailProfile.LONG)

    assert short == {"ref": "node_0001", "kind": "node", "label": "Person", "name": "Marco Bianchi"}
    assert medium["summary"] == "Known friend from university."
    assert medium["resolution_status"] == "existing"
    assert long["aliases"] == ["Marco"]
    assert "backend_id" not in short
    assert "backend_id" not in medium
    assert "backend_id" not in long


@pytest.mark.parametrize(
    ("label", "expected_kind"),
    [
        ("Person", "node"),
        ("Place", "node"),
        ("Event", "node"),
        ("MemoryLog", "memory"),
        ("Claim", "context"),
        ("Perception", "context"),
        ("RelationshipContext", "context"),
        ("RelationshipState", "context"),
        ("ProfileMemory", "context"),
        ("MediaAsset", "media"),
    ],
)
def test_packet_builder_compacts_node_search_results(label: str, expected_kind: str) -> None:
    context = RefContext()
    properties = {
        "id": f"{label.lower()}-1",
        "display_name": "Marco Bianchi",
        "name": "Moon beach",
        "title": "Beach outing",
        "log_text": "The user played Bang Duel with Merc and Bri.",
        "text": "The Moon atmosphere was not great.",
        "relationship_detail": "Close friend context.",
        "profile_key": "communication_style",
        "caption": "Beach photo",
        "metadata": {"raw": "noise"},
        "vector_id": "vector-noise",
        "prompt_trace": "prompt-noise",
        "raw_payload": {"full": "payload"},
    }
    result = NodeSearchResult(label=label, labels=[label], properties=properties)

    packet = build_ref_packet(result, ref_context=context, profile=PacketDetailProfile.MEDIUM)

    assert packet["kind"] == expected_kind
    assert packet["ref"].startswith(f"{expected_kind if expected_kind != 'memory' else 'memory'}_")
    assert "backend_id" not in packet
    assert "metadata" not in packet
    assert "vector_id" not in packet
    assert "prompt_trace" not in packet
    assert "raw_payload" not in packet


def test_packet_builder_exposes_relationship_endpoint_refs() -> None:
    context = RefContext()
    from_entry = context.add_hydrated("node", backend_id="node-from", label="Person", name="Marco")
    to_entry = context.add_hydrated("node", backend_id="node-to", label="Person", name="Lorenzo")
    relationship = RelationshipResult(
        type="BROTHER_OF",
        from_id="node-from",
        to_id="node-to",
        properties={"id": "rel-1", "metadata": {"noise": True}},
    )

    packet = build_ref_packet(relationship, ref_context=context, profile="medium")

    assert packet["kind"] == "edge"
    assert packet["type"] == "BROTHER_OF"
    assert packet["from_ref"] == from_entry.ref
    assert packet["to_ref"] == to_entry.ref
    assert "metadata" not in packet


def test_provider_tool_result_transport_remains_unchanged_for_ref_context() -> None:
    provider_fields = set(ProviderToolResult.model_fields)

    assert {"status", "output", "data", "error", "meta"} <= provider_fields
    assert "ref_context_delta" not in provider_fields
    assert "ref_packets" not in provider_fields


def test_fallback_dict_packet_and_tool_payload_ref_fields() -> None:
    context = RefContext()
    packet = build_ref_packet(
        {
            "id": "memory-1",
            "label": "MemoryLog",
            "log_text": "The user had a beer with Bri before dinner.",
            "source_kind": "user_message",
            "metadata": {"noise": True},
        },
        ref_context=context,
        profile="medium",
    )
    payload = AgenticToolPayload(
        summary="memory_0001 created.",
        created_refs=[packet["ref"]],
        affected_graph_ids=[packet["ref"]],
        ref_context_delta={"created": [packet["ref"]]},
        ref_packets=[packet],
    )

    assert packet["kind"] == "memory"
    assert packet["summary"] == "The user had a beer with Bri before dinner."
    assert packet["source_hint"] == "user_message"
    assert "metadata" not in packet
    assert payload.ref_context_delta == {"created": [packet["ref"]]}
    assert payload.ref_packets == [packet]


def test_memory_contexts_carry_model_facing_ref_packets_without_backend_ids() -> None:
    ref_context = RefContext()
    ref_context.add_hydrated("node", backend_id="node-marco", label="Person", name="Marco")
    conversation = ConversationContext(
        current_message=NeutralConversationMessage.user("Remember I met Marco yesterday."),
    )
    action = MemoryPlanAction(action_type=MemoryPlanActionType.CREATE_NODE)

    ingestion = MemoryCreationContext(
        conversation=conversation,
        action=action,
        ref_context=ref_context,
        ref_packets=[{"ref": "node_0001", "kind": "node", "name": "Marco"}],
    )
    payload = ingestion.model_facing_payload()

    assert payload["ref_context"][0]["ref"] == "node_0001"
    assert payload["ref_packets"][0]["name"] == "Marco"
    assert "backend_id" not in str(payload)
