from __future__ import annotations

import json

import pytest

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

        def generate_chat_with_tools(
            self,
            request,
            *,
            toolbox,
            tools_mapping,
            max_tool_calls=None,
        ) -> None:
            content = request.messages[-1].content
            content = content.removeprefix("```json\n").removesuffix("\n```")
            payload = json.loads(content)
            self.calls.append((len(payload["candidate_actions"]), max_tool_calls))
            for candidate in payload["candidate_actions"]:
                tools_mapping["create_node"](
                    candidate_ref=candidate["local_ref"],
                    payload={},
                    reason="test",
                    evidence_refs=[],
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
