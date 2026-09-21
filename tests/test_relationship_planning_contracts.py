from my_digital_brain.agentic import (
    EdgeMemoryPlan,
    MemoryIngestionReasoning,
    MemoryPlanAction,
    MemoryPlanActionType,
    MemoryPlanningPhase,
    MemoryPlanStep,
    ReasoningAmbiguity,
    RelationshipEvidenceHint,
)
from my_digital_brain.prompts import PromptRegistry


def test_explicit_relationship_evidence_supports_a_typed_edge_action() -> None:
    reasoning = MemoryIngestionReasoning(
        relationship_evidence=[
            RelationshipEvidenceHint(
                from_mention="Elena Pollastrelli",
                to_mention="Matteo Morichetti",
                relationship_summary="partners",
                evidence_text="Elena Pollastrelli and Matteo Morichetti are partners.",
            )
        ]
    )
    plan = EdgeMemoryPlan(
        summary="Store the stated partnership.",
        steps=[
            MemoryPlanStep(
                step_id="edge_partnership_001",
                phase=MemoryPlanningPhase.EDGES,
                actions=[
                    MemoryPlanAction(
                        action_id="relationship_partnership_001",
                        action_type=MemoryPlanActionType.CREATE_RELATIONSHIP,
                        target_refs=["node_elena_pollastrelli", "node_matteo_morichetti"],
                        payload={
                            "from_ref": "node_elena_pollastrelli",
                            "to_ref": "node_matteo_morichetti",
                        },
                    )
                ],
            )
        ],
    )

    assert reasoning.relationship_evidence[0].relationship_summary == "partners"
    assert plan.steps[0].actions[0].action_type == MemoryPlanActionType.CREATE_RELATIONSHIP


def test_co_presence_allows_an_empty_edge_plan() -> None:
    reasoning = MemoryIngestionReasoning(
        planning_guidance=(
            "Keep co-presence in the memory log unless a durable relationship is stated."
        )
    )
    plan = EdgeMemoryPlan(
        summary="No durable relationship is stated; keep the shared outing as involvement.",
        steps=[],
    )

    assert reasoning.relationship_evidence == []
    assert plan.steps == []


def test_ambiguous_relationship_endpoint_stays_out_of_the_edge_plan() -> None:
    reasoning = MemoryIngestionReasoning(
        ambiguities=[
            ReasoningAmbiguity(
                subject="Elena",
                description="The source does not establish which Elena is Matteo's partner.",
            )
        ],
        missing_context_questions=["Which Elena is Matteo's partner?"],
    )
    plan = EdgeMemoryPlan(
        summary="Clarification is required before writing the relationship.",
        steps=[],
    )

    assert reasoning.missing_context_questions == ["Which Elena is Matteo's partner?"]
    assert plan.steps == []


def test_relationship_prompt_distinguishes_explicit_evidence_from_co_presence() -> None:
    prompt = PromptRegistry().load("memory_edge_planning").template

    assert "clearly stated relationship evidence" in prompt
    assert "empty edge plan" in prompt
    assert "co-presence" in prompt
