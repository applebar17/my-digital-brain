from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from my_digital_brain.ai.models import ToolResult as ProviderToolResult
from my_digital_brain.agentic import (
    AgenticStateId,
    ReasoningHighlights,
    ReasoningDuplicateNote,
    ReasoningAmbiguity,
    NodeReasoningHighlights,
    MemoryIngestionReasoning,
    MemoryIngestionContext,
    IrrelevantDetailHint,
    EdgeReasoningHighlights,
    PlannedRefPacket,
    PlanExecutionMode,
    NodePlanPacket,
    NodeMemoryPlan,
    MemoryPlanStep,
    MemoryPlanPacket,
    MemoryPlanningPhase,
    MemoryLogMemoryPlan,
    EdgeMemoryPlan,
    AliasReasoningHint,
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
    assert "chat entry router" in prompt.template
    assert "structured reasoning notes" in default_registry.load(
        "reasoning_checkpoint",
    ).template
    assert "ordered process actions" in default_registry.load(
        "planning_checkpoint",
    ).template
    assert "memory reasoner" in default_registry.load("memory_ingestion").template
    assert "memory action executor" in default_registry.load("memory_creation").template

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
    assert "Pending-process" not in cancel_route.assistant_message.content



def test_conversation_context_has_no_pending_process_fields() -> None:
    context = ConversationContext(
        current_message=NeutralConversationMessage.user("I do not remember"),
    )
    payload = context.model_facing_payload()

    assert "pending_process" not in payload
    assert "pending_processes" not in payload


def test_memory_ingestion_reasoning_contract_accepts_guidance_not_actions() -> None:
    reasoning = MemoryIngestionReasoning(
        highlights=ReasoningHighlights(
            nodes=NodeReasoningHighlights(
                persons="The main people are Lorenzo, Gianluca, Merc, and Bri.",
                places="The beach and Bar Mario are relevant places.",
            ),
            logs=[
                "The user spent the afternoon at the beach with friends.",
                "The user noticed the Moon atmosphere was not great.",
            ],
            edges=EdgeReasoningHighlights(
                family="Lorenzo is described as the user's brother.",
                perception_or_affect="The beach atmosphere may need a perception record.",
            ),
        ),
        possible_aliases=[
            AliasReasoningHint(
                main_mention="Matteo Mercoldi",
                aliases=["Merc"],
                notes="Check existing people before creating a duplicate.",
            ),
        ],
        irrelevant_details=[
            IrrelevantDetailHint(
                detail="Incidental co-presence at the beach should not become durable edges.",
                reason="Weak relationship evidence.",
                category="weak_edge",
            ),
        ],
        ambiguities=[
            ReasoningAmbiguity(
                subject="Fabione",
                description="Nickname may map to Riccardo Cau.",
                possible_interpretations=["Riccardo Cau", "new person"],
            ),
        ],
        duplicate_or_resolution_notes=[
            ReasoningDuplicateNote(
                mention="Bri",
                note="Likely an alias; check existing graph candidates.",
                candidate_refs=["node_0002"],
            ),
        ],
        missing_context_questions=["Which person does Fabione refer to if graph candidates conflict?"],
        planning_guidance="Split dense source text into several compact MemoryLogs.",
    )

    payload = reasoning.model_dump(mode="json")

    assert payload["highlights"]["nodes"]["persons"].startswith("The main people")
    assert payload["possible_aliases"][0]["aliases"] == ["Merc"]
    assert payload["irrelevant_details"][0]["category"] == "weak_edge"
    assert payload["duplicate_or_resolution_notes"][0]["candidate_refs"] == ["node_0002"]


def test_memory_ingestion_reasoning_rejects_empty_payload_and_proposed_refs() -> None:
    with pytest.raises(ValidationError, match="at least one useful signal"):
        MemoryIngestionReasoning()

    with pytest.raises(ValidationError, match="must not allocate proposed refs"):
        MemoryIngestionReasoning(
            highlights=ReasoningHighlights(
                nodes=NodeReasoningHighlights(
                    persons="Create node_new_0001 for Lorenzo.",
                ),
            ),
        )

    with pytest.raises(ValidationError):
        MemoryIngestionReasoning(
            highlights=ReasoningHighlights(logs=["One useful log highlight."]),
            backend_id="node-backend-1",
        )

    with pytest.raises(ValidationError):
        MemoryIngestionReasoning(
            highlights=ReasoningHighlights(logs=["One useful log highlight."]),
            action_type="create_node",
        )


def test_memory_ingestion_context_carries_reasoning_packets_without_backend_ids() -> None:
    ref_context = RefContext()
    ref_context.add_hydrated("node", backend_id="node-backend-marco", label="Person", name="Marco")
    conversation = ConversationContext(
        current_message=NeutralConversationMessage.user("Remember the beach afternoon with Merc."),
    )
    reasoning = MemoryIngestionReasoning(
        highlights=ReasoningHighlights(logs=["The source describes a beach afternoon."]),
        planning_guidance="Keep this as an episodic memory highlight.",
    )

    context = MemoryIngestionContext(
        conversation=conversation,
        reasoning=reasoning,
        reasoning_packets=[{"label": "Hydrated graph context", "packets": [{"ref": "node_0001"}]}],
        ref_context=ref_context,
        ref_packets=[{"ref": "node_0001", "kind": "node", "name": "Marco"}],
    )
    payload = context.model_facing_payload()

    assert payload["reasoning"]["planning_guidance"] == "Keep this as an episodic memory highlight."
    assert payload["reasoning_packets"][0]["label"] == "Hydrated graph context"
    assert payload["ref_context"][0]["ref"] == "node_0001"
    assert "node-backend-marco" not in str(payload)


def test_memory_ingestion_prompt_locks_reasoner_boundary() -> None:
    template = PromptRegistry().load("memory_ingestion").template

    assert "# Context" in template
    assert "# Rules" in template
    assert "# Examples" in template
    assert "Hydrated graph context" in template
    assert "Known aliases and candidate mentions" in template
    assert "do not create refs" in template
    assert "Planning creates refs and actions" in template
    assert "Stay high-level" in template


def test_three_phase_memory_plan_contracts_and_packets_validate() -> None:
    node_action = MemoryPlanAction(
        action_id="node_action_0001",
        action_type=MemoryPlanActionType.CREATE_NODE,
        target_refs=["node_new_0001"],
    )
    node_step = MemoryPlanStep(
        step_id="node_step_0001",
        phase=MemoryPlanningPhase.NODES,
        execution_mode=PlanExecutionMode.PARALLEL,
        actions=[node_action],
    )
    node_plan = NodeMemoryPlan(
        summary="Plan one person node.",
        steps=[node_step],
        node_plan_packet=NodePlanPacket(
            planned_refs=[
                PlannedRefPacket(
                    ref="node_new_0001",
                    object_kind="node",
                    label="Person",
                    name="Marco",
                    aliases=["Marco from university"],
                )
            ],
            summary="Marco is planned for memory hosts.",
        ),
    )
    memory_plan = MemoryLogMemoryPlan(
        summary="Plan one compact memory.",
        steps=[
            MemoryPlanStep(
                step_id="memory_step_0001",
                phase="memory_logs",
                execution_mode="sequential",
                actions=[
                    MemoryPlanAction(
                        action_id="memory_action_0001",
                        action_type="create_memory_log",
                        target_refs=["memory_new_0001", "node_new_0001"],
                    )
                ],
            )
        ],
        memory_plan_packet=MemoryPlanPacket(
            planned_refs=[
                PlannedRefPacket(
                    ref="memory_new_0001",
                    object_kind="memory",
                    label="MemoryLog",
                    summary="Marco was from university.",
                )
            ],
            host_refs=["node_new_0001"],
            involved_refs=["node_new_0001"],
            weak_edge_notes=["Co-presence stays as involvement."],
        ),
    )
    edge_plan = EdgeMemoryPlan(
        summary="Plan one edge.",
        steps=[
            MemoryPlanStep(
                step_id="edge_step_0001",
                phase="edges",
                actions=[
                    MemoryPlanAction(
                        action_id="edge_action_0001",
                        action_type="create_relationship",
                        payload={"from_ref": "node_new_0001", "to_ref": "node_0001"},
                    )
                ],
            )
        ],
    )

    assert node_plan.steps[0].execution_mode == PlanExecutionMode.PARALLEL.value
    assert node_plan.node_plan_packet.planned_refs[0].aliases == ["Marco from university"]
    assert memory_plan.memory_plan_packet.host_refs == ["node_new_0001"]
    assert edge_plan.steps[0].phase == MemoryPlanningPhase.EDGES.value
    assert "backend_id" not in str(node_plan.node_plan_packet.model_dump(mode="json"))

    with pytest.raises(ValidationError):
        EdgeMemoryPlan(
            summary="Invalid edge endpoint.",
            steps=[
                MemoryPlanStep(
                    step_id="edge_step_0002",
                    phase="edges",
                    actions=[
                        MemoryPlanAction(
                            action_id="edge_action_0002",
                            action_type="create_relationship",
                            payload={"from_ref": "Marco", "to_ref": "node_0001"},
                        )
                    ],
                )
            ],
        )


def test_three_phase_planning_prompts_include_handoff_packets() -> None:
    registry = PromptRegistry()
    node = registry.load("memory_node_planning").template
    memory = registry.load("memory_log_planning").template
    edge = registry.load("memory_edge_planning").template

    assert "Reasoning inventory packet" in node
    assert "Known refs" in node
    assert "Existing graph candidates" in node
    assert "Resolve aliases and duplicate candidates" in node

    assert "Node plan packet" in memory
    assert "Irrelevant details" in memory
    assert "weak co-presence as log involvement" in memory

    assert "Node plan packet" in edge
    assert "Memory plan packet" in edge
    assert "Edge endpoints must be known refs" in edge
    assert "never loose names" in edge


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
