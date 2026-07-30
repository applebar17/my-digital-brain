from __future__ import annotations

import json

import pytest

from my_digital_brain.ai.schemas import ChatMessage, ProviderCallMetadata
from my_digital_brain.ai.session import (
    LLMCompletionRequest,
    LLMCompletionResult,
    LLMSessionAwaitingTool,
    LLMSessionCompleted,
    LLMSessionRequest,
    LLMSessionResult,
    LLMSessionRunner,
)
from my_digital_brain.ingestion.contracts import (
    CandidateMemoryGraph,
    IngestionContextPackage,
    MemoryLog,
    ResolutionResult,
    ResolutionStep,
    ResolutionToolAction,
    ResolutionToolName,
)
from my_digital_brain.ingestion.exceptions import IngestionValidationError
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry
from my_digital_brain.ingestion.resolution_agent import LLMResolutionProposalAgent
from my_digital_brain.ingestion.write_plan import GraphWritePlanBuilder


def _memory() -> MemoryLog:
    return MemoryLog(
        local_ref="MEMORY_LOG_001",
        log_text="Marco changed jobs.",
        host_target_ids=["NODE_000001"],
    )


def test_resolution_actions_control_memory_write_shape() -> None:
    graph = CandidateMemoryGraph(source_id="source-1", memory_logs=[_memory()])
    result = ResolutionResult(
        metadata={
            "validated_tool_actions": [
                ResolutionToolAction(
                    step=ResolutionStep.MEMORY,
                    tool_name=ResolutionToolName.UPDATE_MEMORY,
                    candidate_ref="MEMORY_LOG_001",
                    target_ref="NODE_000001",
                ).model_dump(mode="json", exclude_none=True),
            ],
        },
    )

    plan = GraphWritePlanBuilder().build(graph, result)

    assert plan.memory_logs_to_create == []
    assert len(plan.nodes_to_update) == 1
    assert plan.nodes_to_update[0].target_ref == "NODE_000001"


def test_resolution_agent_accepts_configured_tool_call_budget() -> None:
    agent = LLMResolutionProposalAgent(object(), session_max_tool_calls=100)  # type: ignore[arg-type]
    assert agent.session_max_tool_calls == 100
    assert agent.batch_size == 5


def test_resolution_agent_batches_candidates_at_the_tool_call_ceiling() -> None:
    class Provider:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int | None]] = []
            self._emitted = False

        def run_session(self, request: LLMSessionRequest) -> LLMSessionResult:
            self._emitted = False
            return LLMSessionRunner(self).run(request)

        def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
            if self._emitted:
                return LLMCompletionResult(
                    assistant_message=ChatMessage(role="assistant", content="done"),
                    metadata=ProviderCallMetadata.fake(model=request.model),
                )
            content = request.messages[-1].content or ""
            content = content.removeprefix("```json\n").removesuffix("\n```")
            payload = json.loads(content)
            self.calls.append(
                (len(payload["candidate_actions"]), len(payload["candidate_actions"]))
            )
            self._emitted = True
            tool_calls = [
                {
                    "id": f"call-{index}",
                    "type": "function",
                    "function": {
                        "name": "create_node",
                        "arguments": json.dumps(
                            {
                                "candidate_ref": candidate["local_ref"],
                                "payload": {"display_name": "Resolved candidate"},
                                "reason": "test",
                                "evidence_refs": [],
                            }
                        ),
                    },
                }
                for index, candidate in enumerate(payload["candidate_actions"])
            ]
            return LLMCompletionResult(
                assistant_message=ChatMessage(
                    role="assistant",
                    content=None,
                    tool_calls=tool_calls,
                ),
                metadata=ProviderCallMetadata.fake(model=request.model),
            )

    provider = Provider()
    graph = CandidateMemoryGraph(
        source_id="source-1",
        candidate_entities=[
            {
                "local_ref": f"CANDIDATE_PERSON_{index:03d}",
                "entity_type": "Person",
                "display_name": f"Person {index}",
            }
            for index in range(1, 12)
        ],
    )
    actions = LLMResolutionProposalAgent(
        provider,
        session_max_tool_calls=10,
        batch_size=10,
    ).propose(
        step=ResolutionStep.NODE,
        source_text="source",
        context=IngestionContextPackage(source_id="source-1"),
        candidate_graph=graph,
    )

    assert len(actions) == 11
    assert provider.calls == [(10, 10), (1, 1)]


def test_resolution_repairs_missing_actions_in_the_same_session() -> None:
    class Provider:
        def __init__(self) -> None:
            self.turn = 0
            self.requests: list[LLMSessionRequest] = []

        def run_session(self, request: LLMSessionRequest) -> LLMSessionResult:
            self.requests.append(request)
            return LLMSessionRunner(self).run(request)

        def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
            self.turn += 1
            if self.turn == 1:
                return _tool_completion(
                    [_resolution_tool_call("create-1", "create_node", "CANDIDATE_PERSON_001")],
                    request.model,
                )
            if self.turn == 3:
                return _tool_completion(
                    [_resolution_tool_call("create-2", "create_node", "CANDIDATE_PERSON_002")],
                    request.model,
                )
            if self.turn == 5:
                return _tool_completion(
                    [_resolution_tool_call("create-3", "create_node", "CANDIDATE_PERSON_003")],
                    request.model,
                )
            return _text_completion("The current turn is complete.", request.model)

    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    graph = CandidateMemoryGraph(
        source_id="source-1",
        candidate_entities=[
            {
                "local_ref": f"CANDIDATE_PERSON_{index:03d}",
                "entity_type": "Person",
                "display_name": f"Person {index}",
            }
            for index in range(1, 4)
        ],
    )
    provider = Provider()
    agent = LLMResolutionProposalAgent(provider, batch_size=5)

    resolved_map, result = agent.resolve_nodes(
        source_text="I met three people.",
        context=IngestionContextPackage(
            source_id="source-1",
            reference_registry_snapshot=registry.snapshot(),
        ),
        candidate_graph=graph,
    )

    assert [entry.local_ref for entry in resolved_map.entries] == [
        "CANDIDATE_PERSON_001",
        "CANDIDATE_PERSON_002",
        "CANDIDATE_PERSON_003",
    ]
    assert len(result.decisions) == 3
    assert [request.session_id for request in provider.requests] == [
        "resolution-source-1-node-0",
        "resolution-source-1-node-0",
        "resolution-source-1-node-0",
    ]
    repair_messages = [request.messages[-1] for request in provider.requests[1:]]
    assert all(
        message.role == "user"
        and "still requiring exactly one terminal action" in (message.content or "")
        for message in repair_messages
    )
    assert len(repair_messages) == 2
    assert "CANDIDATE_PERSON_002" in repair_messages[0].content
    assert "CANDIDATE_PERSON_003" in repair_messages[1].content


def test_resolution_agent_returns_pending_clarification_to_ingestion() -> None:
    class Provider:
        provider_name = "fake"

        def run_session(self, request: LLMSessionRequest) -> LLMSessionResult:
            return LLMSessionRunner(self).run(request)

        def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
            return LLMCompletionResult(
                assistant_message=ChatMessage(
                    role="assistant",
                    tool_calls=[
                        {
                            "id": "clarify-1",
                            "type": "function",
                            "function": {
                                "name": "ask_clarification",
                                "arguments": json.dumps(
                                    {
                                        "doubts": [
                                            {
                                                "doubt_id": "DOUBT_001",
                                                "doubt": "Amos has no identifying surname.",
                                                "refs": ["CANDIDATE_PERSON_001"],
                                                "missing_information": "Surname",
                                                "why_blocking": "The identity is incomplete.",
                                                "evidence_refs": ["CANDIDATE_PERSON_001"],
                                            }
                                        ]
                                    }
                                ),
                            },
                        }
                    ],
                ),
                metadata=ProviderCallMetadata.fake(model=request.model),
            )

    result = LLMResolutionProposalAgent(Provider()).propose(
        step=ResolutionStep.NODE,
        source_text="I met Amos.",
        context=IngestionContextPackage(source_id="source-1"),
        candidate_graph=CandidateMemoryGraph(
            source_id="source-1",
            candidate_entities=[
                {
                    "local_ref": "CANDIDATE_PERSON_001",
                    "entity_type": "Person",
                    "display_name": "Amos",
                }
            ],
        ),
    )

    assert isinstance(result, LLMSessionAwaitingTool)
    assert result.continuation.pending_tool_calls[0].name == "ask_clarification"
    assert result.continuation.pending_tool_calls[0].call_id == "clarify-1"


def test_resolution_agent_resumes_the_same_session_after_clarification() -> None:
    class Provider:
        def __init__(self) -> None:
            self.turn = 0
            self.session_ids: list[str] = []
            self.requests: list[LLMSessionRequest] = []

        def run_session(self, request: LLMSessionRequest) -> LLMSessionResult:
            self.session_ids.append(request.session_id)
            self.requests.append(request)
            return LLMSessionRunner(self).run(request)

        def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
            self.turn += 1
            if self.turn == 1:
                tool_call = {
                    "id": "clarify-1",
                    "type": "function",
                    "function": {
                        "name": "ask_clarification",
                        "arguments": json.dumps(
                            {
                                "doubts": [
                                    {
                                        "doubt_id": "DOUBT_001",
                                        "doubt": "Amos has no identifying surname.",
                                        "refs": ["CANDIDATE_PERSON_001"],
                                        "missing_information": "Surname",
                                        "why_blocking": "The identity is incomplete.",
                                        "evidence_refs": ["CANDIDATE_PERSON_001"],
                                    }
                                ]
                            }
                        ),
                    },
                }
                message = ChatMessage(role="assistant", tool_calls=[tool_call])
            elif self.turn == 2:
                tool_call = {
                    "id": "create-1",
                    "type": "function",
                    "function": {
                        "name": "create_node",
                        "arguments": json.dumps(
                            {
                                "candidate_ref": "CANDIDATE_PERSON_001",
                                "payload": {"display_name": "Amos Vignaroli"},
                                "reason": "The user identified Amos.",
                                "evidence_refs": ["CANDIDATE_PERSON_001"],
                            }
                        ),
                    },
                }
                message = ChatMessage(role="assistant", tool_calls=[tool_call])
            else:
                message = ChatMessage(role="assistant", content="Resolution complete.")
            return LLMCompletionResult(
                assistant_message=message,
                metadata=ProviderCallMetadata.fake(model=request.model),
            )

    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    context = IngestionContextPackage(
        source_id="source-1",
        reference_registry_snapshot=registry.snapshot(),
    )
    graph = CandidateMemoryGraph(
        source_id="source-1",
        candidate_entities=[
            {
                "local_ref": "CANDIDATE_PERSON_001",
                "entity_type": "Person",
                "display_name": "Amos",
            }
        ],
    )
    provider = Provider()
    agent = LLMResolutionProposalAgent(provider, session_max_tool_calls=10)

    pending = agent.propose(
        step=ResolutionStep.NODE,
        source_text="I met Amos.",
        context=context,
        candidate_graph=graph,
    )
    assert isinstance(pending, LLMSessionAwaitingTool)

    resumed = agent.resume_nodes(
        source_text="I met Amos.",
        context=context,
        candidate_graph=graph,
        continuation=pending.continuation,
        answer_text="Amos Vignaroli",
    )

    assert isinstance(resumed, tuple)
    resolved_map, resolution = resumed
    assert resolved_map.entries[0].local_ref == "CANDIDATE_PERSON_001"
    assert resolution.decisions[0].candidate_ref == "CANDIDATE_PERSON_001"
    assert provider.session_ids == [
        "resolution-source-1-node-0",
        "resolution-source-1-node-0",
    ]
    resumed_messages = provider.requests[1].messages
    assert not any(
        message.role == "user" and "Amos Vignaroli" in (message.content or "")
        for message in resumed_messages
    )
    assert any(
        message.role == "tool" and "Amos Vignaroli" in (message.content or "")
        for message in resumed_messages
    )


def test_resolution_validation_is_scoped_to_the_current_batch_on_resume() -> None:
    class Provider:
        def __init__(self) -> None:
            self.turn = 0
            self.batch_sizes: list[int] = []

        def run_session(self, request: LLMSessionRequest) -> LLMSessionResult:
            return LLMSessionRunner(self).run(request)

        def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
            self.turn += 1
            if self.turn in {1, 3}:
                if self.turn == 1:
                    candidates = json.loads(
                        (request.messages[-1].content or "")
                        .removeprefix("```json\n")
                        .removesuffix("\n```")
                    )["candidate_actions"]
                    self.batch_sizes.append(len(candidates))
                    calls = [
                        _resolution_tool_call(
                            f"create-{candidate['local_ref']}",
                            "create_node",
                            candidate["local_ref"],
                        )
                        for candidate in candidates
                    ]
                else:
                    candidates = json.loads(
                        (request.messages[-1].content or "")
                        .removeprefix("```json\n")
                        .removesuffix("\n```")
                    )["candidate_actions"]
                    self.batch_sizes.append(len(candidates))
                    calls = [
                        _resolution_tool_call(
                            "clarify-011",
                            "ask_clarification",
                            candidates[0]["local_ref"],
                        )
                    ]
                return _tool_completion(calls, request.model)
            if self.turn == 2:
                return _text_completion("first batch complete", request.model)
            if self.turn == 4:
                return _tool_completion(
                    [
                        _resolution_tool_call(
                            "create-011",
                            "create_node",
                            "CANDIDATE_PERSON_011",
                        )
                    ],
                    request.model,
                )
            return _text_completion("second batch complete", request.model)

    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    graph = CandidateMemoryGraph(
        source_id="source-1",
        candidate_entities=[
            {
                "local_ref": f"CANDIDATE_PERSON_{index:03d}",
                "entity_type": "Person",
                "display_name": f"Person {index}",
            }
            for index in range(1, 12)
        ],
    )
    context = IngestionContextPackage(
        source_id="source-1",
        reference_registry_snapshot=registry.snapshot(),
    )
    provider = Provider()
    agent = LLMResolutionProposalAgent(
        provider,
        session_max_tool_calls=10,
        batch_size=10,
    )

    pending = agent.resolve_nodes(
        source_text="I met eleven people.",
        context=context,
        candidate_graph=graph,
    )
    assert isinstance(pending, LLMSessionAwaitingTool)

    resumed = agent.resume_nodes(
        source_text="I met eleven people.",
        context=context,
        candidate_graph=graph,
        continuation=pending.continuation,
        answer_text="The person is identified by the existing context.",
    )

    assert isinstance(resumed, tuple)
    resolved_map, result = resumed
    assert len(resolved_map.entries) == 11
    assert len(result.decisions) == 11
    assert provider.batch_sizes == [10, 1]


def test_resolution_accumulates_actions_across_multiple_clarification_continuations() -> None:
    class Provider:
        def __init__(self) -> None:
            self.turn = 0

        def run_session(self, request: LLMSessionRequest) -> LLMSessionResult:
            return LLMSessionRunner(self).run(request)

        def complete(self, request: LLMCompletionRequest) -> LLMCompletionResult:
            self.turn += 1
            if self.turn == 1:
                return _tool_completion(
                    [
                        _resolution_tool_call("create-1", "create_node", "CANDIDATE_PERSON_001"),
                        _resolution_tool_call(
                            "clarify-2", "ask_clarification", "CANDIDATE_PERSON_002"
                        ),
                        _resolution_tool_call("create-3", "create_node", "CANDIDATE_PERSON_003"),
                    ],
                    request.model,
                )
            if self.turn == 2:
                return _tool_completion(
                    [_resolution_tool_call("create-2", "create_node", "CANDIDATE_PERSON_002")],
                    request.model,
                )
            return _text_completion("All candidate actions are complete.", request.model)

    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    graph = CandidateMemoryGraph(
        source_id="source-1",
        candidate_entities=[
            {
                "local_ref": f"CANDIDATE_PERSON_{index:03d}",
                "entity_type": "Person",
                "display_name": f"Person {index}",
            }
            for index in range(1, 4)
        ],
    )
    context = IngestionContextPackage(
        source_id="source-1",
        reference_registry_snapshot=registry.snapshot(),
    )
    agent = LLMResolutionProposalAgent(Provider(), session_max_tool_calls=10)

    pending = agent.resolve_nodes(
        source_text="I met three people.",
        context=context,
        candidate_graph=graph,
    )
    assert isinstance(pending, LLMSessionAwaitingTool)

    resumed = agent.resume_nodes(
        source_text="I met three people.",
        context=context,
        candidate_graph=graph,
        continuation=pending.continuation,
        answer_text="The person is identified by the supplied context.",
    )

    assert isinstance(resumed, tuple)
    resolved_map, result = resumed
    assert [entry.local_ref for entry in resolved_map.entries] == [
        "CANDIDATE_PERSON_001",
        "CANDIDATE_PERSON_002",
        "CANDIDATE_PERSON_003",
    ]
    assert len(result.decisions) == 3


def _resolution_tool_call(call_id: str, name: str, candidate_ref: str) -> dict:
    if name == "ask_clarification":
        arguments = {
            "doubts": [
                {
                    "doubt_id": f"DOUBT_{candidate_ref}",
                    "doubt": "The candidate identity needs user clarification.",
                    "refs": [candidate_ref],
                    "missing_information": "Identity information.",
                    "why_blocking": "The candidate cannot be resolved safely yet.",
                    "evidence_refs": [candidate_ref],
                }
            ]
        }
    else:
        arguments = {
            "candidate_ref": candidate_ref,
            "reason": "The supplied evidence supports this resolution.",
            "evidence_refs": [candidate_ref],
        }
    if name == "create_node":
        arguments["payload"] = {"display_name": "Resolved candidate"}
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def _tool_completion(calls: list[dict], model: str | None) -> LLMCompletionResult:
    return LLMCompletionResult(
        assistant_message=ChatMessage(role="assistant", tool_calls=calls),
        metadata=ProviderCallMetadata.fake(model=model),
    )


def _text_completion(content: str, model: str | None) -> LLMCompletionResult:
    return LLMCompletionResult(
        assistant_message=ChatMessage(role="assistant", content=content),
        metadata=ProviderCallMetadata.fake(model=model),
    )


def test_resolution_agent_replays_clarification_history_as_transcript_messages() -> None:
    class Provider:
        def __init__(self) -> None:
            self.request: LLMSessionRequest | None = None

        def run_session(self, request: LLMSessionRequest) -> LLMSessionResult:
            self.request = request
            return LLMSessionCompleted(
                session_id=request.session_id,
                messages=request.messages,
                content="done",
            )

    provider = Provider()
    agent = LLMResolutionProposalAgent(provider)

    with pytest.raises(ValueError, match="still requiring exactly one terminal action"):
        agent.propose(
            step=ResolutionStep.NODE,
            source_text="I met Jacopo.",
            context=IngestionContextPackage(
                source_id="source-1",
                metadata={
                    "model_facing_history": [
                        {
                            "role": "assistant",
                            "content": "Clarification needed: Which Jacopo?",
                        },
                        {
                            "role": "user",
                            "content": "Clarification answer: Jacopo Galletta.",
                        },
                    ],
                },
            ),
            candidate_graph=CandidateMemoryGraph(
                source_id="source-1",
                candidate_entities=[
                    {
                        "local_ref": "CANDIDATE_PERSON_001",
                        "entity_type": "Person",
                        "display_name": "Jacopo Galletta",
                    }
                ],
            ),
        )

    assert provider.request is not None
    assert [message.content for message in provider.request.messages[:3]] == [
        "I met Jacopo.",
        "Clarification needed: Which Jacopo?",
        "Clarification answer: Jacopo Galletta.",
    ]


def test_missing_structured_node_decision_never_defaults_to_creation() -> None:
    graph = CandidateMemoryGraph(
        source_id="source-1",
        candidate_entities=[
            {
                "local_ref": "CANDIDATE_PERSON_001",
                "entity_type": "Person",
                "display_name": "Marco",
            },
        ],
    )

    with pytest.raises(IngestionValidationError, match="omitted a candidate decision"):
        GraphWritePlanBuilder().build(graph, ResolutionResult())
