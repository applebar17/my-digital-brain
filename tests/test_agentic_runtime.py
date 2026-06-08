from __future__ import annotations

from typing import Any

from my_digital_brain.agentic import (
    AgenticRuntime,
    AgenticPlanningService,
    AgenticReasoningService,
    AgenticStateId,
    AgenticStateInvocation,
    AgenticStateRunner,
    AgenticToolExecutionContext,
    ChannelSessionMetadata,
    ConversationContext,
    CorrectionIntakeContext,
    NeutralConversationMessage,
    PendingProcessContext,
    PlanningActionContext,
    PlanningPurposeGuidelines,
    PlanningTransformContext,
    PlanningTransformResultContext,
    QueryRetrievalPlanningContext,
    ReasoningCheckpointContext,
    ReasoningPurposeGuidelines,
)
from my_digital_brain.ai.schemas import ChatRequest, ChatResult, ProviderCallMetadata
from my_digital_brain.ai.schemas import StructuredGenerationRequest, StructuredGenerationResult
from my_digital_brain.ai.tools import ToolBox
from my_digital_brain.chat.enums import ChatResponseStatus
from my_digital_brain.chat.facade import ChatToolRequest, ChatToolResult


class ScriptedToolCallingProvider:
    provider_name = "scripted"

    def __init__(
        self,
        steps: list[dict[str, Any]],
        *,
        structured_payloads: list[dict[str, Any]] | None = None,
    ) -> None:
        self.steps = list(steps)
        self.structured_payloads = list(structured_payloads or [])
        self.calls: list[dict[str, Any]] = []
        self.structured_calls: list[StructuredGenerationRequest] = []

    def generate_chat_with_tools(
        self,
        request: ChatRequest,
        *,
        toolbox: ToolBox,
        tools_mapping: dict[str, Any],
        max_tool_calls: int | None = None,
    ) -> ChatResult:
        step = self.steps.pop(0) if self.steps else {"content": ""}
        self.calls.append(
            {
                "request": request,
                "toolbox": toolbox,
                "tool_names": sorted(toolbox.tools_by_name),
                "max_tool_calls": max_tool_calls,
            }
        )
        tool_name = step.get("tool")
        if tool_name:
            assert tool_name in toolbox.tools_by_name
            tools_mapping[tool_name](**step.get("arguments", {}))
        return ChatResult(
            content=step.get("content", ""),
            metadata=ProviderCallMetadata.fake(model=request.model),
        )

    def generate_chat(self, request: ChatRequest) -> ChatResult:
        return ChatResult(
            content="plain chat",
            metadata=ProviderCallMetadata.fake(model=request.model),
        )

    def generate_structured(
        self,
        request: StructuredGenerationRequest,
    ) -> StructuredGenerationResult:
        self.structured_calls.append(request)
        payload = self.structured_payloads.pop(0)
        parsed = request.output_schema.model_validate(payload)
        return StructuredGenerationResult(
            parsed=parsed,
            metadata=ProviderCallMetadata.fake(model=request.model),
        )


class FakeGraphService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def get_context_package(
        self,
        node_id: str,
        *,
        include_history: bool = True,
        timeline_limit: int = 20,
        relationship_limit: int = 50,
    ) -> dict[str, Any]:
        self.calls.append(("get_context_package", node_id))
        return {
            "target": {"alias": "NODE_000001", "title": "Marco"},
            "current_facts": [{"description": "University friend"}],
            "alias_map": {"NODE_000001": node_id},
        }


class FakeBackendFacade:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ChatToolRequest]] = []

    def start_memory_ingestion(self, request: ChatToolRequest) -> ChatToolResult:
        self.calls.append(("start_memory_ingestion", request))
        return ChatToolResult(
            status=ChatResponseStatus.ACCEPTED,
            primary_text="Memory accepted by backend.",
            metadata={"operation": "start_memory_ingestion"},
        )


def _conversation(text: str = "What do I remember about Marco?") -> ConversationContext:
    return ConversationContext(
        current_message=NeutralConversationMessage.user(text),
        history=[
            NeutralConversationMessage.user("I met Marco yesterday."),
            NeutralConversationMessage.assistant("I received this memory."),
        ],
        timezone="Europe/Rome",
        channel_metadata=ChannelSessionMetadata(
            channel="telegram",
            conversation_id="chat-1",
            owner_id="owner-1",
            session_id="session-1",
            sender_id="sender-1",
        ),
    )


def _runner(provider: ScriptedToolCallingProvider) -> AgenticStateRunner:
    return AgenticStateRunner(provider=provider)


def test_conversation_entry_without_tool_call_returns_terminal_assistant_response() -> None:
    provider = ScriptedToolCallingProvider(
        [{"content": "I can help you store or query memories."}]
    )
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(_conversation("hello"), AgenticToolExecutionContext())

    assert result.status == "ok"
    assert result.final_text == "I can help you store or query memories."
    assert result.visited_states == [AgenticStateId.CONVERSATION_ENTRY.value]
    assert result.state_results[0].terminal is True
    prompt_payload = provider.calls[0]["request"].messages[1].content
    assert "channel_metadata" not in str(prompt_payload)
    assert provider.calls[0]["tool_names"] == [
        "propose_memory_correction",
        "query_memory_context",
        "start_memory_ingestion",
    ]


def test_conversation_entry_query_tool_hands_off_to_memory_query_state() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Routing to memory query.",
                "tool": "query_memory_context",
                "arguments": {
                    "question": "What do I remember about Marco?",
                    "seed_id": "node-marco",
                },
            },
            {
                "content": "Marco is stored as your university friend.",
                "tool": "get_context_package",
                "arguments": {"node_id": "node-marco"},
            },
            {"content": "Marco is stored as your university friend."},
        ]
    )
    graph = FakeGraphService()
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(
        _conversation(),
        AgenticToolExecutionContext(graph_service=graph),
    )

    assert result.status == "ok"
    assert result.final_text == "Marco is stored as your university friend."
    assert result.visited_states == [
        AgenticStateId.CONVERSATION_ENTRY.value,
        AgenticStateId.MEMORY_QUERY.value,
        AgenticStateId.CONVERSATION_ENTRY.value,
    ]
    assert result.state_results[0].handoff_target == "memory_query"
    assert result.state_results[1].tool_events[0].tool_name == "get_context_package"
    assert graph.calls == [("get_context_package", "node-marco")]
    assert provider.calls[0]["max_tool_calls"] == 3
    assert provider.calls[0]["tool_names"] == [
        "propose_memory_correction",
        "query_memory_context",
        "start_memory_ingestion",
    ]
    assert provider.calls[2]["tool_names"] == []
    assert provider.calls[2]["max_tool_calls"] == 0
    assert '"owner_finalization": true' in provider.calls[2]["request"].messages[1].content


def test_correction_handoff_reaches_confirmation_aware_specialist_state() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Routing to correction intake.",
                "tool": "propose_memory_correction",
                "arguments": {
                    "correction_text": "Marco was from university, not work.",
                    "target_id": "node-marco",
                },
            },
            {
                "content": "Should I update Marco?",
                "tool": "request_user_confirmation",
                "arguments": {
                    "question": "Should I update Marco?",
                    "proposal": {"target_id": "node-marco", "field_path": "description"},
                    "target_refs": ["node-marco"],
                },
            },
        ]
    )
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(
        _conversation("Marco was from university, not work."),
        AgenticToolExecutionContext(),
    )

    assert result.status == "ok"
    assert result.visited_states == [
        AgenticStateId.CONVERSATION_ENTRY.value,
        AgenticStateId.CORRECTION_INTAKE.value,
    ]
    confirmation = result.state_results[1].tool_events[0].data["confirmation"]
    assert confirmation["required_user_action"] == "confirm_or_cancel"
    assert confirmation["proposal"]["target_id"] == "node-marco"


def test_pending_context_starts_from_pending_process_review() -> None:
    provider = ScriptedToolCallingProvider(
        [{"content": "Which Marco did you mean?"}]
    )
    runtime = AgenticRuntime(_runner(provider))
    conversation = _conversation("I am not sure")
    conversation.pending_process = PendingProcessContext(
        process_id="process-1",
        kind="memory_ingestion",
        status="pending",
        question="Which Marco?",
    )

    result = runtime.run(conversation, AgenticToolExecutionContext())

    assert result.visited_states == [AgenticStateId.PENDING_PROCESS_REVIEW.value]
    assert provider.calls[0]["tool_names"] == [
        "cancel_pending_process",
        "pause_pending_process",
        "propose_memory_correction",
        "query_memory_context",
        "request_user_clarification",
        "resume_pending_process",
        "start_memory_ingestion",
    ]


def test_missing_graph_dependency_produces_tool_error_without_crashing() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "I could not retrieve memory context.",
                "tool": "get_context_package",
                "arguments": {"node_id": "node-marco"},
            }
        ]
    )
    runner = _runner(provider)
    query_context = QueryRetrievalPlanningContext(
        question="What about Marco?",
        conversation=_conversation("What about Marco?"),
    )

    result = runner.run_state(
        AgenticStateInvocation(
            state_id=AgenticStateId.MEMORY_QUERY,
            context_payload=query_context,
            execution_context=AgenticToolExecutionContext(),
        )
    )

    assert result.status == "error"
    assert result.assistant_text == "I could not retrieve memory context."
    assert result.tool_events[0].error["code"] == "missing_dependency"
    assert "graph_service" in result.tool_events[0].error["hint"]


def test_clarification_tool_interrupts_without_error_status() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "I need to ask a clarification.",
                "tool": "request_user_clarification",
                "arguments": {
                    "reason": "Two memory targets are plausible.",
                    "compact_summary": "Need target disambiguation.",
                    "target_refs": ["NODE_000001", "NODE_000002"],
                    "questions": [
                        {
                            "question": "Which target should I use?",
                            "options": [
                                {"label": "First target", "recommended": True},
                                {"label": "Second target"},
                            ],
                            "free_text_allowed": True,
                            "required": True,
                            "selection_mode": "single",
                        }
                    ],
                },
            }
        ]
    )
    runner = _runner(provider)
    query_context = QueryRetrievalPlanningContext(
        question="Which Marco?",
        conversation=_conversation("Which Marco?"),
    )

    result = runner.run_state(
        AgenticStateInvocation(
            state_id=AgenticStateId.MEMORY_QUERY,
            context_payload=query_context,
            execution_context=AgenticToolExecutionContext(),
        )
    )

    assert result.status == "ok"
    assert result.tool_events[0].status == "needs_user_input"
    assert result.tool_events[0].data["pending_process"]["question"] == (
        "Which target should I use?"
    )


def test_ingestion_handoff_delegates_to_backend_facade() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Routing to ingestion.",
                "tool": "start_memory_ingestion",
                "arguments": {"source_text": "Yesterday I met Marco."},
            },
            {"content": "I stored that memory."},
        ]
    )
    facade = FakeBackendFacade()
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(
        _conversation("Yesterday I met Marco."),
        AgenticToolExecutionContext(
            backend_facade=facade,
            session_id="session-1",
            conversation_id="conversation-1",
            owner_id="owner-1",
        ),
    )

    assert result.status == "ok"
    assert result.final_text == "I stored that memory."
    assert facade.calls[0][1].text == "Yesterday I met Marco."
    assert result.compact_trace[-2]["backend_process"] == "memory_ingestion_precheck"
    assert result.visited_states == [
        AgenticStateId.CONVERSATION_ENTRY.value,
        AgenticStateId.CONVERSATION_ENTRY.value,
    ]


def test_max_state_transition_limit_prevents_runaway_handoffs() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Routing to memory query.",
                "tool": "query_memory_context",
                "arguments": {"question": "What about Marco?"},
            }
        ]
    )
    runtime = AgenticRuntime(_runner(provider), max_state_transitions=1)

    result = runtime.run(_conversation(), AgenticToolExecutionContext())

    assert result.status == "max_transitions_exceeded"
    assert result.visited_states == [AgenticStateId.CONVERSATION_ENTRY.value]


def test_state_runner_accepts_specialist_context_and_records_tool_events() -> None:
    provider = ScriptedToolCallingProvider(
        [
            {
                "content": "Correction proposal prepared.",
                "tool": "build_correction_proposal",
                "arguments": {
                    "correction_text": "Marco was from university.",
                    "target_id": "node-marco",
                    "reason": "The user provided a direct correction.",
                },
            }
        ]
    )
    runner = _runner(provider)
    correction_context = CorrectionIntakeContext(
        correction_text="Marco was from university.",
        conversation=_conversation("Marco was from university."),
        target_hints=["node-marco"],
    )

    result = runner.run_state(
        AgenticStateInvocation(
            state_id=AgenticStateId.CORRECTION_INTAKE,
            context_payload=correction_context,
            execution_context=AgenticToolExecutionContext(),
        )
    )

    assert result.status == "ok"
    assert result.tool_events[0].tool_name == "build_correction_proposal"
    assert result.tool_events[0].data["proposal"]["requires_confirmation"] is True


def test_reasoning_checkpoint_service_runs_structured_state() -> None:
    provider = ScriptedToolCallingProvider(
        [],
        structured_payloads=[
            {
                "checkpoint_id": "checkpoint-1",
                "purpose_id": "memory_storage_precheck",
                "summary": "The memory contains an owner relationship to Alessia.",
                "insights": [
                    {
                        "insight_type": "relationship_intent",
                        "summary": "The phrase 'my girlfriend' expresses a relationship.",
                        "evidence_text": "Alessia is my girlfriend",
                    }
                ],
                "entity_understandings": [
                    {
                        "mention_text": "Alessia",
                        "interpretation": "Person anchor mentioned by the user.",
                        "should_be_node": True,
                        "possible_node_type": "Person",
                    }
                ],
                "storage_recommendations": [
                    {
                        "subject": "Alessia relationship",
                        "recommendation_type": "create_relationship_context",
                        "reason": "The user described a meaningful personal relationship.",
                        "guardrails": ["Backend must decide owner/self graph representation."],
                    }
                ],
                "next_context_summary": (
                    "Preserve Alessia as a person anchor and girlfriend as relationship detail."
                ),
            }
        ],
    )
    service = AgenticReasoningService(_runner(provider))
    context = ReasoningCheckpointContext(
        checkpoint_id="checkpoint-1",
        purpose=ReasoningPurposeGuidelines(
            purpose_id="memory_storage_precheck",
            goal="Identify owner references and node-versus-metadata choices.",
            focus_areas=["owner relationship", "node versus metadata"],
        ),
        conversation=_conversation("Alessia is my girlfriend."),
        input_context={"source_text": "Alessia is my girlfriend."},
        timezone="Europe/Rome",
    )

    result = service.reason(context, AgenticToolExecutionContext())

    assert result.status == "ok"
    assert result.state_id == AgenticStateId.REASONING_CHECKPOINT.value
    assert result.structured_output is not None
    assert result.structured_output["purpose_id"] == "memory_storage_precheck"
    assert result.structured_output["insights"][0]["insight_type"] == "relationship_intent"
    structured_call = provider.structured_calls[0]
    assert structured_call.context.purpose == "reasoning_checkpoint"
    assert structured_call.output_schema.__name__ == "ReasoningCheckpointResultContext"
    assert structured_call.input_message["context"]["purpose"]["focus_areas"] == [
        "owner relationship",
        "node versus metadata",
    ]


def test_planning_checkpoint_service_runs_structured_state() -> None:
    provider = ScriptedToolCallingProvider(
        [],
        structured_payloads=[
            {
                "planning_id": "planning-1",
                "purpose_id": "entity_ingestion_planning",
                "summary": "Plan one entity action for Matteo Mercoldi.",
                "actions": [
                    {
                        "action_ref": "ACTION_001",
                        "goal": "Extract Matteo Mercoldi as one person candidate.",
                        "action_kind": "extract_entity",
                        "target_refs": ["NODE_000001"],
                        "evidence_text": "Merc is Matteo Mercoldi.",
                    }
                ],
                "next_context_summary": "Merc is an alias hint for Matteo Mercoldi.",
            }
        ],
    )
    service = AgenticPlanningService(_runner(provider))
    context = PlanningTransformContext(
        planning_id="planning-1",
        purpose=PlanningPurposeGuidelines(
            purpose_id="entity_ingestion_planning",
            goal="Plan entity extraction without relationships.",
            focus_areas=["aliases", "duplicate hints"],
        ),
        input_context={
            "source_text": "Merc is Matteo Mercoldi.",
            "graph_context_view": {"aliases": ["Merc -> Matteo Mercoldi"]},
        },
        reasoning_artifact={
            "summary": "Merc is a nickname for Matteo Mercoldi.",
        },
        timezone="Europe/Rome",
    )

    result = service.plan(context, output_schema=PlanningTransformResultContext)

    assert result.status == "ok"
    assert result.state_id == AgenticStateId.PLANNING_CHECKPOINT.value
    assert result.structured_output is not None
    assert result.structured_output["purpose_id"] == "entity_ingestion_planning"
    assert result.structured_output["actions"][0]["action_ref"] == "ACTION_001"
    structured_call = provider.structured_calls[0]
    assert structured_call.context.purpose == "planning_checkpoint"
    assert structured_call.output_schema.__name__ == "PlanningTransformResultContext"
    assert structured_call.input_message["context"]["expected_output_schema"] == (
        "PlanningTransformResultContext"
    )


def test_contradiction_review_question_becomes_pending_process_hint() -> None:
    provider = ScriptedToolCallingProvider(
        [{"content": "Review support complete."}],
        structured_payloads=[
            {
                "judge_request_id": "judge-1",
                "intent": "needs_clarification",
                "decision": "needs_clarification",
                "severity": "high",
                "reason": "The same event appears to have two mutually exclusive places.",
                "graph_action": "ask_user",
                "clarification_question": "Was the meeting in Milan or Turin?",
                "affected_refs": ["NODE_000001"],
                "source_refs": ["SOURCE_000001"],
            }
        ],
    )
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(
        _conversation("I met Marco in Milan."),
        AgenticToolExecutionContext(),
        start_state=AgenticStateId.CONTRADICTION_REVIEW,
    )

    assert result.visited_states == [
        AgenticStateId.CONTRADICTION_REVIEW.value,
        AgenticStateId.CONTRADICTION_REVIEW.value,
    ]
    assert result.pending_process_hints[0]["kind"] == "memory_ingestion"
    assert result.pending_process_hints[0]["question"] == "Was the meeting in Milan or Turin?"
    assert result.metadata["contradiction_intent"] == "needs_clarification"
    assert provider.structured_calls[0].output_schema.__name__ == (
        "ContradictionJudgeResultContext"
    )


def test_contradiction_review_free_form_question_without_structured_intent_is_not_pending() -> None:
    provider = ScriptedToolCallingProvider(
        [{"content": "This looks suspicious. Which city was correct?"}],
        structured_payloads=[
            {
                "judge_request_id": "judge-1",
                "intent": "emit_verdict",
                "decision": "nuance",
                "severity": "low",
                "reason": "The wording can be stored as nuance rather than a blocking conflict.",
                "graph_action": "allow_write",
            }
        ],
    )
    runtime = AgenticRuntime(_runner(provider))

    result = runtime.run(
        _conversation("I met Marco in Milan."),
        AgenticToolExecutionContext(),
        start_state=AgenticStateId.CONTRADICTION_REVIEW,
    )

    assert result.pending_process_hints == []
    assert result.status == "ok"
    assert result.metadata["contradiction_intent"] == "emit_verdict"
