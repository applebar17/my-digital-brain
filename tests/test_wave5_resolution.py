from __future__ import annotations

import json

import pytest

from my_digital_brain.ai.schemas import ChatMessage, ProviderCallMetadata
from my_digital_brain.ai.session import (
    LLMCompletionRequest,
    LLMCompletionResult,
    LLMSessionAwaitingTool,
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


def test_resolution_agent_enforces_ten_call_wave5_ceiling() -> None:
    agent = LLMResolutionProposalAgent(object(), max_tool_calls=100)  # type: ignore[arg-type]
    assert agent.max_tool_calls == 10


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
                                "payload": {},
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
    actions = LLMResolutionProposalAgent(provider).propose(
        step=ResolutionStep.NODE,
        source_text="source",
        context=IngestionContextPackage(source_id="source-1"),
        candidate_graph=graph,
    )

    assert len(actions) == 11
    assert provider.calls == [(10, 10), (1, 1)]


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
                                        "candidate_ref": "CANDIDATE_PERSON_001",
                                        "question": "Qual è il cognome?",
                                        "options": ["Non ricordo"],
                                        "reason": "The identity is incomplete.",
                                        "evidence_refs": ["CANDIDATE_PERSON_001"],
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
    assert result.continuation.pending_tool_call.name == "ask_clarification"
    assert result.continuation.pending_tool_call.call_id == "clarify-1"


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
