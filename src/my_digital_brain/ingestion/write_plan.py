from __future__ import annotations

from my_digital_brain.graph.constants import OWNER_ALIAS
from my_digital_brain.ingestion.contracts import (
    CandidateMemoryGraph,
    GraphNodeWrite,
    GraphRelationshipWrite,
    GraphWritePlan,
    IngestionContextPackage,
    ResolutionDecision,
    ResolutionResult,
    ResolutionStep,
    ResolutionToolAction,
)
from my_digital_brain.ingestion.enums import GraphWritePlanStatus, ResolutionDecisionType
from my_digital_brain.ingestion.exceptions import IngestionValidationError
from my_digital_brain.ingestion.write_plan_serializers import GraphWriteSerializersMixin
from my_digital_brain.ingestion.resolution_write_actions import ResolutionWriteActions
from my_digital_brain.ingestion.write_plan_helpers import (
    _memory_log_links,
)


def _required_action(
    actions: ResolutionWriteActions | None,
    step: ResolutionStep,
    candidate_ref: str,
) -> ResolutionToolAction | None:
    if actions is None:
        return None
    action = actions.for_ref(step, candidate_ref)
    if action is None:
        raise IngestionValidationError(
            f"No validated {step.value} resolution action exists for {candidate_ref}."
        )
    return action


class GraphWritePlanBuilder(GraphWriteSerializersMixin):
    """Build deterministic, backend-owned graph write commands."""

    def build(
        self,
        candidate_graph: CandidateMemoryGraph,
        resolution: ResolutionResult,
        context: IngestionContextPackage | None = None,
    ) -> GraphWritePlan:
        if resolution.clarifications:
            raise IngestionValidationError(
                "Cannot build graph write plan while resolution requires clarification."
            )
        if candidate_graph.candidate_profile_memories and (
            context is None or OWNER_ALIAS not in context.aliases
        ):
            raise IngestionValidationError(
                "Profile memory writes require the backend OWNER alias mapping."
            )

        decision_by_ref = {decision.candidate_ref: decision for decision in resolution.decisions}
        resolution_actions = ResolutionWriteActions.from_result(resolution)
        idempotency_keys: list[str] = []
        nodes_to_create: list[GraphNodeWrite] = []
        relationships_to_create: list[GraphRelationshipWrite] = []
        claims_to_create: list[GraphNodeWrite] = []
        perceptions_to_create: list[GraphNodeWrite] = []
        relationship_contexts_to_create: list[GraphNodeWrite] = []
        nodes_to_update: list[GraphNodeWrite] = []
        memory_logs_to_create: list[GraphNodeWrite] = []
        profile_memories_to_create: list[GraphNodeWrite] = []
        relationships_to_update: list[GraphRelationshipWrite] = []
        planned_ref_ids = self._local_ref_resolution(resolution)

        for entity in candidate_graph.candidate_entities:
            decision = decision_by_ref.get(entity.local_ref)
            if _decision_type(decision) == ResolutionDecisionType.MATCH_EXISTING:
                continue
            if _decision_type(decision) in {
                ResolutionDecisionType.REJECT,
                ResolutionDecisionType.KEEP_PENDING,
            }:
                continue
            if _decision_type(decision) == ResolutionDecisionType.ASK_CLARIFICATION:
                raise IngestionValidationError(
                    f"Candidate {entity.local_ref} still requires clarification."
                )
            write = self._entity_write(candidate_graph.source_id, entity)
            nodes_to_create.append(write)
            planned_ref_ids[entity.local_ref] = str(write.properties["id"])
            idempotency_keys.append(write.idempotency_key or "")

        for claim in candidate_graph.candidate_claims:
            claim_write = self._claim_write(candidate_graph.source_id, claim)
            claims_to_create.append(claim_write)
            planned_ref_ids[claim.local_ref] = str(claim_write.properties["id"])
            idempotency_keys.append(claim_write.idempotency_key or "")
            for index, about_ref in enumerate(claim.about_refs):
                relationship = self._relationship_write(
                    source_id=candidate_graph.source_id,
                    local_ref=f"{claim.local_ref}_ABOUT_{index + 1:03d}",
                    relationship_type="ABOUT",
                    from_ref=claim.local_ref,
                    to_ref=about_ref,
                    candidate=claim,
                )
                relationships_to_create.append(relationship)
                idempotency_keys.append(relationship.idempotency_key or "")

        for perception in candidate_graph.candidate_perceptions:
            perception_write = self._perception_write(candidate_graph.source_id, perception)
            perceptions_to_create.append(perception_write)
            planned_ref_ids[perception.local_ref] = str(perception_write.properties["id"])
            idempotency_keys.append(perception_write.idempotency_key or "")
            relationship = self._relationship_write(
                source_id=candidate_graph.source_id,
                local_ref=f"{perception.local_ref}_PERCEPTION_OF",
                relationship_type="PERCEPTION_OF",
                from_ref=perception.local_ref,
                to_ref=perception.target_ref,
                candidate=perception,
            )
            relationships_to_create.append(relationship)
            idempotency_keys.append(relationship.idempotency_key or "")

        for context_candidate in candidate_graph.candidate_relationship_contexts:
            action = _required_action(
                resolution_actions,
                ResolutionStep.RELATIONSHIP,
                context_candidate.local_ref,
            )
            if ResolutionWriteActions.is_skip(action):
                continue
            context_write = self._relationship_context_write(
                candidate_graph.source_id,
                context_candidate,
            )
            if ResolutionWriteActions.is_update(action):
                nodes_to_update.append(ResolutionWriteActions.node_update(context_write, action))
            else:
                relationship_contexts_to_create.append(context_write)
            planned_ref_ids[context_candidate.local_ref] = str(context_write.properties["id"])
            idempotency_keys.append(context_write.idempotency_key or "")
            if action is not None and ResolutionWriteActions.is_update(action):
                continue
            for index, endpoint_ref in enumerate(
                (context_candidate.from_ref, context_candidate.to_ref),
            ):
                relationship = self._relationship_write(
                    source_id=candidate_graph.source_id,
                    local_ref=f"{context_candidate.local_ref}_WITH_{index + 1:03d}",
                    relationship_type="RELATIONSHIP_WITH",
                    from_ref=context_candidate.local_ref,
                    to_ref=endpoint_ref,
                    candidate=context_candidate,
                )
                relationships_to_create.append(relationship)
                idempotency_keys.append(relationship.idempotency_key or "")

        for memory_log in candidate_graph.memory_logs:
            action = _required_action(
                resolution_actions,
                ResolutionStep.MEMORY,
                memory_log.local_ref or memory_log.memory_log_id,
            )
            if ResolutionWriteActions.is_skip(action):
                continue
            memory_log_write = self._memory_log_write(
                candidate_graph.source_id,
                memory_log,
                planned_ref_ids,
            )
            if ResolutionWriteActions.is_update(action):
                nodes_to_update.append(ResolutionWriteActions.node_update(memory_log_write, action))
            else:
                memory_logs_to_create.append(memory_log_write)
            planned_ref_ids[memory_log_write.local_ref] = str(memory_log_write.properties["id"])
            idempotency_keys.append(memory_log_write.idempotency_key or "")
            if not ResolutionWriteActions.is_update(action):
                for index, link in enumerate(_memory_log_links(memory_log)):
                    relationship = self._memory_log_relationship_write(
                        source_id=candidate_graph.source_id,
                        memory_log=memory_log,
                        link=link,
                        index=index,
                    )
                    relationships_to_create.append(relationship)
                    idempotency_keys.append(relationship.idempotency_key or "")

        for profile in candidate_graph.candidate_profile_memories:
            action = _required_action(
                resolution_actions,
                ResolutionStep.MEMORY,
                profile.local_ref,
            )
            if ResolutionWriteActions.is_skip(action):
                continue
            profile_write = self._profile_memory_write(candidate_graph.source_id, profile)
            if ResolutionWriteActions.is_update(action):
                nodes_to_update.append(ResolutionWriteActions.node_update(profile_write, action))
            else:
                profile_memories_to_create.append(profile_write)
            planned_ref_ids[profile.local_ref] = str(profile_write.properties["id"])
            idempotency_keys.append(profile_write.idempotency_key or "")
            if not ResolutionWriteActions.is_update(action):
                relationship = self._relationship_write(
                    source_id=candidate_graph.source_id,
                    local_ref=f"{profile.local_ref}_DESCRIBES_USER",
                    relationship_type="DESCRIBES_USER",
                    from_ref=profile.local_ref,
                    to_ref="OWNER",
                    candidate=profile,
                )
                relationships_to_create.append(relationship)
                idempotency_keys.append(relationship.idempotency_key or "")

        for relationship in candidate_graph.candidate_relationships:
            action = _required_action(
                resolution_actions,
                ResolutionStep.RELATIONSHIP,
                relationship.local_ref,
            )
            if ResolutionWriteActions.is_skip(action):
                continue
            relationship_write = self._candidate_relationship_write(
                candidate_graph.source_id,
                relationship,
            )
            if ResolutionWriteActions.is_update(action):
                relationships_to_update.append(
                    ResolutionWriteActions.relationship_endpoints(relationship_write, action)
                )
            else:
                relationships_to_create.append(relationship_write)
            idempotency_keys.append(relationship_write.idempotency_key or "")

        return GraphWritePlan(
            source_id=candidate_graph.source_id,
            status=GraphWritePlanStatus.DRAFT,
            nodes_to_create=nodes_to_create,
            nodes_to_update=nodes_to_update,
            relationships_to_create=relationships_to_create,
            relationships_to_update=relationships_to_update,
            claims_to_create=claims_to_create,
            perceptions_to_create=perceptions_to_create,
            relationship_contexts_to_create=relationship_contexts_to_create,
            memory_logs_to_create=memory_logs_to_create,
            profile_memories_to_create=profile_memories_to_create,
            metadata_patches=list(candidate_graph.candidate_metadata_patches),
            evidence_links=list(candidate_graph.evidence_refs),
            idempotency_keys=sorted(key for key in set(idempotency_keys) if key),
            resolution_decisions=list(resolution.decisions),
            metadata={
                "candidate_graph_id": candidate_graph.candidate_graph_id,
                "alias_map": (context.aliases if context else {}),
                "reference_registry_snapshot": (
                    context.reference_registry_snapshot if context else {}
                ),
                "local_ref_resolution": self._local_ref_resolution(resolution),
            },
        )

    def _local_ref_resolution(self, resolution: ResolutionResult) -> dict[str, str]:
        return {
            decision.candidate_ref: decision.target_entity_id
            for decision in resolution.decisions
            if decision.target_entity_id
        }


def _decision_type(decision: ResolutionDecision | None) -> ResolutionDecisionType:
    if decision is None:
        raise IngestionValidationError(
            "The structured resolution proposal omitted a candidate decision."
        )
    return ResolutionDecisionType(decision.decision_type)
