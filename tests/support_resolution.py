from __future__ import annotations

from my_digital_brain.ingestion.contracts import (
    CandidateMemoryGraph,
    IngestionContextPackage,
    ResolutionStep,
    ResolutionToolAction,
    ResolutionToolName,
)
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry
from my_digital_brain.ingestion.resolution_proposals import (
    ResolutionProposalCompiler,
    ResolutionProposalValidator,
)


class FixedResolutionAgent:
    """Test double that emits structured actions, never semantic fallbacks."""

    def __init__(
        self,
        *,
        clarify: bool = False,
        node_action: str = "create",
        target_ref: str | None = None,
    ) -> None:
        self.clarify = clarify
        self.node_action = node_action
        self.target_ref = target_ref

    def resolve_nodes(
        self,
        *,
        source_text: str | None,
        context: IngestionContextPackage,
        candidate_graph: CandidateMemoryGraph,
        packets=(),
    ):
        registry = RunReferenceRegistry.from_snapshot(context.reference_registry_snapshot)
        actions = []
        for entity in candidate_graph.candidate_entities:
            if self.clarify:
                actions.append(
                    ResolutionToolAction(
                        step=ResolutionStep.NODE,
                        tool_name=ResolutionToolName.ASK_CLARIFICATION,
                        candidate_ref=entity.local_ref,
                        question="Which supplied person did you mean?",
                    ),
                )
            elif self.node_action == "update":
                actions.append(
                    ResolutionToolAction(
                        step=ResolutionStep.NODE,
                        tool_name=ResolutionToolName.UPDATE_NODE,
                        candidate_ref=entity.local_ref,
                        target_ref=self.target_ref,
                    ),
                )
            else:
                actions.append(
                    ResolutionToolAction(
                        step=ResolutionStep.NODE,
                        tool_name=ResolutionToolName.CREATE_NODE,
                        candidate_ref=entity.local_ref,
                    ),
                )
        compiler = ResolutionProposalCompiler(ResolutionProposalValidator(registry))
        result = compiler.compile(actions, candidate_graph=candidate_graph, packets=packets)
        return compiler.build_entity_map(candidate_graph, result), result

    def propose(
        self,
        *,
        step: ResolutionStep,
        source_text: str | None,
        context: IngestionContextPackage,
        candidate_graph: CandidateMemoryGraph,
        packets=(),
    ) -> list[ResolutionToolAction]:
        if step == ResolutionStep.MEMORY:
            candidates = [
                *candidate_graph.memory_logs,
                *candidate_graph.candidate_profile_memories,
            ]
            return [
                ResolutionToolAction(
                    step=step,
                    tool_name=ResolutionToolName.CREATE_MEMORY,
                    candidate_ref=candidate.local_ref or candidate.memory_log_id,
                )
                for candidate in candidates
            ]
        candidates = [
            *candidate_graph.candidate_relationships,
            *candidate_graph.candidate_relationship_contexts,
        ]
        return [
            ResolutionToolAction(
                step=step,
                tool_name=ResolutionToolName.CREATE_RELATIONSHIP,
                candidate_ref=candidate.local_ref,
                from_ref=candidate.from_ref,
                to_ref=candidate.to_ref,
            )
            for candidate in candidates
        ]
