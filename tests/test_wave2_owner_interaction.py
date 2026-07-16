from __future__ import annotations

import pytest

from my_digital_brain.agentic.contexts import (
    GraphContextPackage,
    ProfileMemoryCandidateContext,
    ProfileMemoryCategory,
    ProfileMemoryStability,
    ProfileMemoryVisibility,
    ReasoningCheckpointContext,
    ReasoningPurposeGuidelines,
)
from my_digital_brain.core.owner_context import OwnerSnapshot
from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    CandidateMemoryGraph,
    CandidateProfileMemory,
    GraphContextPack,
    GraphContextRenderPurpose,
    ExtractionTask,
    IngestionContextPackage,
    SourceRecordRef,
)
from my_digital_brain.ingestion.context_rendering import GraphContextPackRendererService
from my_digital_brain.ingestion.contracts.resolution import ResolutionResult
from my_digital_brain.ingestion.prompt_builders import IngestionPromptBuilder
from my_digital_brain.ingestion.validation import IngestionValidator
from my_digital_brain.ingestion.write_plan import GraphWritePlanBuilder
from my_digital_brain.prompts import PromptRegistry


def test_owner_snapshot_is_minimal_and_preserves_available_identity() -> None:
    snapshot = OwnerSnapshot.from_properties(
        {
            "display_name": "Ada Lovelace",
            "normalized_name": "ada lovelace",
            "aliases": ["Ada", "the owner"],
            "description": "must not be exposed",
        },
    )

    assert snapshot.ref == "OWNER"
    assert snapshot.display_name == "Ada Lovelace"
    assert snapshot.aliases == ["Ada", "the owner"]
    assert "description" not in snapshot.model_dump()


def test_rendered_ingestion_context_always_carries_owner_snapshot() -> None:
    snapshot = OwnerSnapshot(display_name="Ada Lovelace", aliases=["Ada"])
    pack = GraphContextPack(source_id="source-1", owner_snapshot=snapshot)
    view = GraphContextPackRendererService().render(
        pack,
        GraphContextRenderPurpose.RELATIONSHIP_PLANNING,
    )

    assert view.owner_snapshot == snapshot


def test_ingestion_prompt_exposes_owner_contract_without_persisted_id() -> None:
    context = IngestionContextPackage(
        source_id="source-1",
        aliases={"OWNER": "person:owner"},
        owner_snapshot=OwnerSnapshot(display_name="Ada Lovelace"),
    )
    payload = IngestionPromptBuilder().extraction_input(
        source=SourceRecordRef(
            source_id="source-1",
            source_type="text",
            channel="manual",
            raw_text="I am introverted.",
        ),
        task=ExtractionTask(
            task_type="person",
            target_ref="PERSON_001",
            evidence_text="I am introverted.",
        ),
        context=context,
    )

    assert "OWNER" in payload["owner_context"]
    assert "person:owner" not in payload["owner_context"]


def test_agentic_reasoning_context_carries_owner_snapshot() -> None:
    snapshot = OwnerSnapshot(display_name="Ada Lovelace")
    context = ReasoningCheckpointContext(
        purpose=ReasoningPurposeGuidelines(goal="Classify the source."),
        graph_context=GraphContextPackage(owner_snapshot=snapshot),
        owner_snapshot=snapshot,
    )

    assert context.model_facing_payload()["owner_snapshot"]["ref"] == "OWNER"


def test_owner_person_creation_and_profile_data_on_person_are_rejected() -> None:
    candidate_graph = CandidateMemoryGraph(
        source_id="source-1",
        candidate_entities=[
            CandidateEntity(
                local_ref="PERSON_001",
                entity_type="Person",
                typed_properties={"is_owner": True, "personality": "introvert"},
                source_refs=["source-1"],
            ),
        ],
    )

    result = IngestionValidator().validate_candidate_graph(candidate_graph)
    codes = {issue.code for issue in result.issues}
    assert "owner_creation_forbidden" in codes


def test_profile_candidate_requires_provenance_and_inferred_confirmation() -> None:
    with pytest.raises(ValueError, match="original_user_words"):
        CandidateProfileMemory(
            local_ref="PROFILE_001",
            profile_key="personality",
            category="personality",
            value="introvert",
            source_refs=["source-1"],
            reason="inferred",
            original_user_words="",
        )

    candidate = CandidateProfileMemory(
        local_ref="PROFILE_001",
        profile_key="personality",
        category="personality",
        value="introvert",
        source_refs=["source-1"],
        reason="inferred from repeated self-description",
        original_user_words="I prefer quiet groups.",
        assertion_mode="inferred",
    )
    assert candidate.requires_confirmation is True


def test_profile_write_plan_connects_profile_memory_to_owner() -> None:
    candidate = CandidateProfileMemory(
        local_ref="PROFILE_001",
        profile_key="personality",
        category="personality",
        value="introvert",
        source_refs=["source-1"],
        reason="explicit self-statement",
        original_user_words="I'm an introvert.",
    )
    graph = CandidateMemoryGraph(
        source_id="source-1",
        candidate_profile_memories=[candidate],
    )
    plan = GraphWritePlanBuilder().build(
        graph,
        ResolutionResult(decisions=[]),
        IngestionContextPackage(source_id="source-1", aliases={"OWNER": "person:owner"}),
    )

    assert plan.profile_memories_to_create[0].label == "ProfileMemory"
    assert any(
        relationship.relationship_type == "DESCRIBES_USER"
        and relationship.to_ref == "OWNER"
        for relationship in plan.relationships_to_create
    )
    assert IngestionValidator().validate_write_plan(plan).is_valid


def test_profile_agentic_candidate_rejects_temporary_observation() -> None:
    with pytest.raises(ValueError, match="Temporary"):
        ProfileMemoryCandidateContext(
            profile_key="mood",
            category=ProfileMemoryCategory.PERSONALITY,
            value="sad",
            description="temporary mood",
            original_user_words="I feel sad today.",
            source_refs=["source-1"],
            stability=ProfileMemoryStability.TEMPORARY,
            visibility=ProfileMemoryVisibility.HIDDEN,
            reason="isolated event",
        )


def test_owner_prompt_contract_is_registered_for_profile_extraction() -> None:
    prompt = PromptRegistry().load("profile_memory_extraction")
    assert "OWNER" in prompt.template
    assert "DESCRIBES_USER" in prompt.template
