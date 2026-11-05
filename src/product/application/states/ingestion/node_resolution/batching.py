"""Deterministic type-aware batching for node candidates."""

from collections import defaultdict

from pydantic import TypeAdapter

from product.application.references import ReferenceContext, ReferenceObjectKind
from product.application.states.ingestion.node_candidate import NodeCandidate, NodeCandidateSetDTO
from product.application.states.ingestion.node_resolution.models import (
    NodeBatchPolicyDTO,
    NodeCandidateBatchDTO,
    ReferencedNodeCandidateDTO,
)
from product.graph import GRAPH_LABEL_BY_NODE_TYPE, NodeCreate, NodeType
from product.graph.presentation import node_display_name

_NODE_ADAPTER = TypeAdapter(NodeCreate)


class NodeCandidateBatchPlanner:
    """Allocate candidate refs and partition them through one deterministic policy."""

    def __init__(self, policy: NodeBatchPolicyDTO) -> None:
        self.policy = policy

    def plan(
        self,
        candidates: NodeCandidateSetDTO,
        reference_context: ReferenceContext,
    ) -> list[NodeCandidateBatchDTO]:
        """Build dedicated and mixed batches while preserving source order within types."""
        referenced = [
            self._register_candidate(candidate, reference_context)
            for candidate in candidates.candidates
        ]
        groups: dict[NodeType, list[ReferencedNodeCandidateDTO]] = defaultdict(list)
        type_order: list[NodeType] = []
        for item in referenced:
            node_type = item.candidate.node_type
            if node_type not in groups:
                type_order.append(node_type)
            groups[node_type].append(item)

        planned_groups: list[list[ReferencedNodeCandidateDTO]] = []
        leftovers: list[ReferencedNodeCandidateDTO] = []
        maximum = self.policy.maximum_batch_size
        dedicated_minimum = self.policy.dedicated_type_minimum
        for node_type in type_order:
            remaining = list(groups[node_type])
            while len(remaining) >= maximum:
                planned_groups.append(remaining[:maximum])
                remaining = remaining[maximum:]
            if len(remaining) >= dedicated_minimum:
                planned_groups.append(remaining)
            else:
                leftovers.extend(remaining)

        for start in range(0, len(leftovers), maximum):
            planned_groups.append(leftovers[start : start + maximum])

        return [
            NodeCandidateBatchDTO(
                batch_id=f"node_batch_{index:04d}",
                node_types=self._node_types(group),
                candidates=group,
            )
            for index, group in enumerate(planned_groups, start=1)
        ]

    @staticmethod
    def _register_candidate(
        candidate: NodeCandidate,
        reference_context: ReferenceContext,
    ) -> ReferencedNodeCandidateDTO:
        node = _NODE_ADAPTER.validate_python(
            candidate.model_dump(exclude={"identity_gaps"})
        )
        entry = reference_context.allocate_proposed(
            object_kind=ReferenceObjectKind.CANDIDATE,
            label=GRAPH_LABEL_BY_NODE_TYPE[node.node_type],
            display_name=node_display_name(node),
            summary=node.description,
            aliases=node.aliases,
        )
        return ReferencedNodeCandidateDTO(candidate_ref=entry.ref, candidate=candidate)

    @staticmethod
    def _node_types(group: list[ReferencedNodeCandidateDTO]) -> list[NodeType]:
        result: list[NodeType] = []
        for item in group:
            if item.candidate.node_type not in result:
                result.append(item.candidate.node_type)
        return result


def candidate_to_node(candidate: NodeCandidate) -> NodeCreate:
    """Map one candidate to its canonical typed graph creation contract."""
    return _NODE_ADAPTER.validate_python(
        candidate.model_dump(exclude={"identity_gaps"})
    )
