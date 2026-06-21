from __future__ import annotations

import pytest
from pydantic import ValidationError

from my_digital_brain.agentic import (
    AgenticStateId,
    ConfirmationRiskLevel,
    ContradictionDecision,
    ContradictionGraphAction,
    ContradictionJudgeResultContext,
    ContradictionResultIntent,
    ContradictionReviewContext,
    ContradictionSeverity,
    ConversationContext,
    GraphContextPackage,
    GraphUpdateContext,
    MaintenanceReviewContext,
    MaintenanceReviewResultContext,
    MaintenanceSuggestionContext,
    MaintenanceSuggestionType,
    NeutralConversationMessage,
    ProfileExtractionContext,
    ProfileExtractionResultContext,
    ProfileMemoryCandidateContext,
    ProfileMemoryCategory,
    ProfileMemoryStability,
    ProfileMemoryVisibility,
    SourceContext,
    default_state_configs,
)
from my_digital_brain.prompts import PromptRegistry


def _conversation(text: str = "Actually, Marco was from university.") -> ConversationContext:
    return ConversationContext(current_message=NeutralConversationMessage.user(text))


def test_wave3_agentic_state_configs_are_registered_with_safe_toolboxes() -> None:
    configs = default_state_configs()

    graph_update = configs[AgenticStateId.GRAPH_UPDATE]
    contradiction = configs[AgenticStateId.CONTRADICTION_REVIEW]

    assert graph_update.prompt_id == "graph_update"
    assert graph_update.required_context_type == "GraphUpdateContext"
    assert "create_memory_log" in graph_update.allowed_tools
    assert "delete_graph_node" in graph_update.forbidden_tools

    assert contradiction.prompt_id == "contradiction_review"
    assert contradiction.required_context_type == "ContradictionReviewContext"
    assert "get_target_evidence" in contradiction.allowed_tools
    assert "create_contradiction_record" in contradiction.forbidden_tools


def test_wave3_prompt_templates_are_registered() -> None:
    registry = PromptRegistry()

    assert "graph update agent" in registry.load("graph_update").template
    assert "contradiction reviewer" in registry.load("contradiction_review").template
    assert "Tool error" in registry.load("graph_update").template
    assert "Ground the decision" in registry.load("contradiction_review").template


def test_graph_update_context_carries_guidelines_and_target_hints() -> None:
    context = GraphUpdateContext(
        source_text="Marco was from university, not work.",
        conversation=_conversation(),
        guidelines="Apply this as a correction.",
        desired_work="correct_or_update_memory_graph",
        target_ids=["node-marco"],
        graph_context=GraphContextPackage(aliases={"NODE_000001": "node-marco"}),
    )

    assert context.source_text == "Marco was from university, not work."
    assert context.guidelines == "Apply this as a correction."
    assert context.desired_work == "correct_or_update_memory_graph"
    assert context.target_ids == ["node-marco"]
    assert context.graph_context.aliases == {"NODE_000001": "node-marco"}


def test_contradiction_review_requires_grounded_doubt_and_clarification_question() -> None:
    review = ContradictionReviewContext(
        proposed_write_ref="WRITE_000001",
        graph_context=GraphContextPackage(known_ambiguities=["Marco has two likely matches."]),
        affected_entity_refs=["NODE_000001"],
        source_refs=["SOURCE_000001"],
        agent_doubt="The proposed place is Milan, but existing event context says Turin.",
    )
    result = ContradictionJudgeResultContext(
        judge_request_id=review.judge_request_id,
        intent=ContradictionResultIntent.NEEDS_CLARIFICATION,
        decision=ContradictionDecision.NEEDS_CLARIFICATION,
        severity=ContradictionSeverity.HIGH,
        reason="Two mutually exclusive places are attached to what appears to be the same event.",
        graph_action=ContradictionGraphAction.ASK_USER,
        clarification_question="Was the meeting in Milan or Turin?",
        inspected_context_refs=["NODE_000001", "SOURCE_000001"],
    )

    assert result.requires_user_input is True
    assert result.intent == ContradictionResultIntent.NEEDS_CLARIFICATION.value
    assert result.decision == ContradictionDecision.NEEDS_CLARIFICATION.value

    with pytest.raises(ValidationError, match="proposed write"):
        ContradictionReviewContext(agent_doubt="Potential conflict without write context.")

    with pytest.raises(ValidationError, match="clarification_question"):
        ContradictionJudgeResultContext(
            judge_request_id=review.judge_request_id,
            intent=ContradictionResultIntent.NEEDS_CLARIFICATION,
            decision=ContradictionDecision.NEEDS_CLARIFICATION,
            severity=ContradictionSeverity.MEDIUM,
            reason="Needs the user.",
            graph_action=ContradictionGraphAction.ASK_USER,
        )

    with pytest.raises(ValidationError, match="emit_verdict"):
        ContradictionJudgeResultContext(
            judge_request_id=review.judge_request_id,
            intent=ContradictionResultIntent.EMIT_VERDICT,
            decision=ContradictionDecision.NEEDS_CLARIFICATION,
            severity=ContradictionSeverity.MEDIUM,
            reason="This cannot be both final and clarification-seeking.",
            graph_action=ContradictionGraphAction.ASK_USER,
            clarification_question="Which place was correct?",
        )


def test_profile_memory_contracts_preserve_evidence_and_visibility_policy() -> None:
    source = SourceContext(
        source_id="source-1",
        normalized_text="I prefer direct answers and I care about auditability.",
    )
    context = ProfileExtractionContext(
        source=source,
        conversation=_conversation("I prefer direct answers."),
        current_profile_summary="The user prefers pragmatic engineering discussion.",
    )
    candidate = ProfileMemoryCandidateContext(
        profile_key="communication.directness",
        category=ProfileMemoryCategory.COMMUNICATION,
        value="Prefers direct answers.",
        description="The user explicitly asked for direct communication.",
        original_user_words="I prefer direct answers",
        source_refs=["source-1"],
        evidence_text="I prefer direct answers",
        stability=ProfileMemoryStability.USER_CONFIRMED,
        visibility=ProfileMemoryVisibility.PROMPT_ALLOWED,
        requires_confirmation=False,
        reason="Explicit user statement.",
    )
    result = ProfileExtractionResultContext(
        source_id=context.source.source_id,
        candidates=[candidate],
        summary="One explicit communication preference.",
    )

    assert result.candidates[0].profile_key == "communication.directness"
    assert result.candidates[0].visibility == ProfileMemoryVisibility.PROMPT_ALLOWED.value
    assert result.candidates[0].source_refs == ["source-1"]


def test_maintenance_review_contract_requires_suggestion_or_no_action_reason() -> None:
    context = MaintenanceReviewContext(
        trigger="manual_review",
        target_refs=["NODE_000001"],
        graph_context=GraphContextPackage(aliases={"NODE_000001": "node-marco"}),
    )
    suggestion = MaintenanceSuggestionContext(
        suggestion_type=MaintenanceSuggestionType.REVIEW_CONTRADICTION,
        target_refs=context.target_refs,
        reason="A contradiction was detected and should be reviewed before mutation.",
        recommended_action="Ask the user one focused clarification.",
        evidence_refs=["SOURCE_000001"],
        requires_confirmation=True,
        risk_level=ConfirmationRiskLevel.LOW,
    )
    result = MaintenanceReviewResultContext(
        review_id=context.review_id,
        suggestions=[suggestion],
    )

    assert result.suggestions[0].suggestion_type == (
        MaintenanceSuggestionType.REVIEW_CONTRADICTION.value
    )

    with pytest.raises(ValidationError, match="suggestions or no_action_reason"):
        MaintenanceReviewResultContext(review_id=context.review_id)
