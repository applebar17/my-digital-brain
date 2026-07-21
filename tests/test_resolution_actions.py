from __future__ import annotations

import pytest
from pydantic import ValidationError

from my_digital_brain.ingestion import (
    CandidateEntity,
    CandidateMemoryGraph,
    ResolutionProposalCompiler,
    ResolutionProposalValidationError,
    ResolutionProposalValidator,
    ResolutionStep,
    ResolutionToolAction,
    ResolutionToolName,
    RunReferenceRegistry,
    build_resolution_toolbox,
)
from my_digital_brain.ingestion.contracts import (
    EntityLookupCandidate,
    EntityLookupContextPacket,
    EntityLookupResult,
    ExtractionTask,
    IdentityLookupStatus,
    IdentityMatchKind,
    IngestionContextPackage,
    SourceRecordRef,
)
from my_digital_brain.ingestion.enums import SourceChannel, SourceType
from my_digital_brain.ingestion.prompt_builders import IngestionPromptBuilder


def _registry() -> RunReferenceRegistry:
    registry = RunReferenceRegistry(graph_scope="graph-1", run_scope="run-1")
    registry.register_owner("person:owner")
    registry.register_existing(
        "person:marco",
        object_kind="node",
        label="Person",
        display_label="Marco Bianchi",
        aliases=["Marco"],
    )
    return registry


def _graph() -> CandidateMemoryGraph:
    return CandidateMemoryGraph(
        source_id="source-1",
        candidate_entities=[
            CandidateEntity(
                local_ref="CANDIDATE_PERSON_001",
                entity_type="Person",
                display_name="Marco",
            ),
        ],
    )


def test_toolboxes_are_scoped_to_the_resolution_step() -> None:
    node_names = [tool["function"]["name"] for tool in build_resolution_toolbox(ResolutionStep.NODE).tools]
    memory_names = [tool["function"]["name"] for tool in build_resolution_toolbox(ResolutionStep.MEMORY).tools]
    relationship_names = [tool["function"]["name"] for tool in build_resolution_toolbox(ResolutionStep.RELATIONSHIP).tools]

    assert node_names == ["ask_clarification", "create_node", "update_node", "defer_or_ignore"]
    assert memory_names == ["ask_clarification", "create_memory", "update_memory", "defer_or_ignore"]
    assert relationship_names == ["ask_clarification", "create_relationship", "update_relationship", "defer_or_ignore"]


def test_tool_action_rejects_wrong_step_tool_and_missing_clarification_question() -> None:
    with pytest.raises(ValidationError, match="not available"):
        ResolutionToolAction(
            step=ResolutionStep.NODE,
            tool_name=ResolutionToolName.CREATE_MEMORY,
            candidate_ref="CANDIDATE_PERSON_001",
        )
    with pytest.raises(ValidationError, match="requires a question"):
        ResolutionToolAction(
            step=ResolutionStep.NODE,
            tool_name=ResolutionToolName.ASK_CLARIFICATION,
            candidate_ref="CANDIDATE_PERSON_001",
        )


def test_compiler_accepts_supplied_fuzzy_candidate_without_semantic_fallback() -> None:
    registry = _registry()
    action = ResolutionToolAction(
        step=ResolutionStep.NODE,
        tool_name=ResolutionToolName.UPDATE_NODE,
        candidate_ref="CANDIDATE_PERSON_001",
        target_ref="NODE_000001",
        reason="The university context identifies the supplied candidate.",
    )
    compiler = ResolutionProposalCompiler(ResolutionProposalValidator(registry))
    result = compiler.compile([action], candidate_graph=_graph())
    entity_map = compiler.build_entity_map(_graph(), result)

    assert result.decisions[0].target_entity_id == "person:marco"
    assert entity_map.relationship_usable_refs == {"CANDIDATE_PERSON_001": "NODE_000001"}
    assert result.metadata["policy"] == "llm_selected_action_backend_validated"


def test_compiler_turns_clarification_tool_call_into_blocking_session_request() -> None:
    registry = _registry()
    action = ResolutionToolAction(
        step=ResolutionStep.NODE,
        tool_name=ResolutionToolName.ASK_CLARIFICATION,
        candidate_ref="CANDIDATE_PERSON_001",
        question="Which Marco did you mean?",
        options=["Marco Bianchi", "A different Marco"],
        reason="The supplied candidates remain indistinguishable.",
    )
    compiler = ResolutionProposalCompiler(ResolutionProposalValidator(registry))
    result = compiler.compile([action], candidate_graph=_graph())

    assert result.clarification is not None
    assert result.clarification.blocking is True
    assert result.clarification.target_refs == ["CANDIDATE_PERSON_001"]
    assert result.clarification.metadata["source"] == "ask_clarification"


def test_validator_rejects_invented_refs_and_owner_creation() -> None:
    registry = _registry()
    validator = ResolutionProposalValidator(registry)
    action = ResolutionToolAction(
        step=ResolutionStep.NODE,
        tool_name=ResolutionToolName.CREATE_NODE,
        candidate_ref="CANDIDATE_PERSON_001",
        payload={"is_owner": True},
    )
    with pytest.raises(ResolutionProposalValidationError, match="cannot create an owner"):
        validator.validate(action, supplied_candidate_refs={"CANDIDATE_PERSON_001"})

    invented_target = ResolutionToolAction(
        step=ResolutionStep.NODE,
        tool_name=ResolutionToolName.UPDATE_NODE,
        candidate_ref="CANDIDATE_PERSON_001",
        target_ref="NODE_999999",
    )
    with pytest.raises(ResolutionProposalValidationError, match="unknown"):
        validator.validate(invented_target, supplied_candidate_refs={"CANDIDATE_PERSON_001"})

    backend_id_payload = ResolutionToolAction(
        step=ResolutionStep.NODE,
        tool_name=ResolutionToolName.CREATE_NODE,
        candidate_ref="CANDIDATE_PERSON_001",
        payload={"node_id": "person:marco"},
    )
    with pytest.raises(ResolutionProposalValidationError, match="Stable Person"):
        validator.validate(backend_id_payload, supplied_candidate_refs={"CANDIDATE_PERSON_001"})


def test_prompt_adds_match_guidance_only_when_contextual_matches_exist() -> None:
    source = SourceRecordRef(
        source_id="source-1",
        source_type=SourceType.TEXT,
        channel=SourceChannel.MANUAL,
        raw_text="I met Marco.",
    )
    task = ExtractionTask(task_type="person", target_ref="CANDIDATE_PERSON_001")
    no_match_context = IngestionContextPackage(source_id=source.source_id)
    no_match_payload = IngestionPromptBuilder().extraction_input(source, task, no_match_context)

    assert no_match_payload["resolution_context"]["available_tools"] == [
        "ask_clarification",
        "create_node",
        "update_node",
        "defer_or_ignore",
    ]
    assert "match_resolution_guidance" not in no_match_payload["resolution_context"]

    match_context = IngestionContextPackage(
        source_id=source.source_id,
        identity_lookup_packets=[
            EntityLookupContextPacket(
                candidate_ref="CANDIDATE_PERSON_001",
                entity_type="Person",
                lookup=EntityLookupResult(
                    candidate_ref="CANDIDATE_PERSON_001",
                    status=IdentityLookupStatus.ONE_CANDIDATE,
                    candidates=[
                        EntityLookupCandidate(
                            ref="NODE_000001",
                            label="Person",
                            display_name="Marco Bianchi",
                            match_kind=IdentityMatchKind.FUZZY_HINT,
                        ),
                    ],
                ),
            ),
        ],
    )
    match_payload = IngestionPromptBuilder().extraction_input(source, task, match_context)

    assert "match_resolution_guidance" in match_payload["resolution_context"]
    assert "Contextual matches are evidence" in match_payload["resolution_context"]["match_resolution_guidance"]
