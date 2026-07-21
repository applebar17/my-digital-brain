from __future__ import annotations

import pytest

from my_digital_brain.ingestion.contracts import (
    CandidateMemoryGraph,
    IngestionResult,
    MemoryLog,
    ResolutionResult,
    ResolutionStep,
    ResolutionToolAction,
    ResolutionToolName,
)
from my_digital_brain.ingestion.enums import IngestionStatus
from my_digital_brain.ingestion.resolution_agent import LLMResolutionProposalAgent
from my_digital_brain.ingestion.resolution_proposals import (
    ResolutionProposalCompiler,
    ResolutionProposalValidator,
)
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry
from my_digital_brain.ingestion.session_store import InMemoryIngestionProcessStore
from my_digital_brain.ingestion.write_plan import GraphWritePlanBuilder
from my_digital_brain.ingestion.exceptions import IngestionValidationError


def _memory() -> MemoryLog:
    return MemoryLog(
        local_ref="MEMORY_LOG_001",
        log_text="Marco changed jobs.",
        host_target_ids=["NODE_000001"],
    )


def test_multiple_clarifications_survive_compilation_and_session_snapshot() -> None:
    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    compiler = ResolutionProposalCompiler(ResolutionProposalValidator(registry))
    result = compiler.merge_step_actions(
        ResolutionResult(),
        [
            ResolutionToolAction(
                step=ResolutionStep.MEMORY,
                tool_name=ResolutionToolName.ASK_CLARIFICATION,
                candidate_ref="MEMORY_LOG_001",
                question="Should this update Marco's timeline?",
            ),
            ResolutionToolAction(
                step=ResolutionStep.MEMORY,
                tool_name=ResolutionToolName.ASK_CLARIFICATION,
                candidate_ref="MEMORY_LOG_001",
                question="Which date did this happen?",
            ),
        ],
        step=ResolutionStep.MEMORY,
        supplied_candidate_refs={"MEMORY_LOG_001"},
    )

    assert [item.question for item in result.clarifications] == [
        "Should this update Marco's timeline?",
        "Which date did this happen?",
    ]
    snapshot = InMemoryIngestionProcessStore().record_result(
        IngestionResult(
            source_id="source-1",
            status=IngestionStatus.NEEDS_CLARIFICATION,
            clarifications=result.clarifications,
        ),
    )
    assert snapshot.pending_questions == [
        "Should this update Marco's timeline?",
        "Which date did this happen?",
    ]


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
