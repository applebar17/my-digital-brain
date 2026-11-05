"""Prepare current identity evidence and references for one resolution batch."""

from product.application.references import (
    OwnerContextDTO,
    ReferenceContext,
    ReferenceObjectKind,
)
from product.application.states.ingestion.node_resolution.batching import candidate_to_node
from product.application.states.ingestion.node_resolution.models import (
    CandidateIdentityEvidenceDTO,
    IdentityMatchEvidenceDTO,
    NodeCandidateBatchDTO,
    NodeResolutionStateInputDTO,
)
from product.graph import GRAPH_LABEL_BY_NODE_TYPE
from product.graph.identity import GraphIdentityLookupService
from product.graph.presentation import node_display_name


class NodeResolutionBatchPreparer:
    """Run fresh lookup and build one model-safe state input over shared references."""

    def __init__(
        self,
        *,
        owner_id: str,
        identity_lookup: GraphIdentityLookupService,
        reference_context: ReferenceContext,
    ) -> None:
        self.owner_id = owner_id
        self.identity_lookup = identity_lookup
        self.reference_context = reference_context

    def prepare(
        self,
        batch: NodeCandidateBatchDTO,
        owner: OwnerContextDTO,
    ) -> NodeResolutionStateInputDTO:
        """Look up every candidate immediately before its batch invocation.

        Dependencies:
            `GraphIdentityLookupService` returns trusted backend evidence.
            `ReferenceContext` converts every matching backend node to a stable
            model-facing reference shared with prior and later batches.
        """
        evidence: list[CandidateIdentityEvidenceDTO] = []
        selected_refs: list[str] = [owner.id]
        for item in batch.candidates:
            selected_refs.append(item.candidate_ref)
            lookup = self.identity_lookup.lookup(
                self.owner_id,
                candidate_to_node(item.candidate),
            )
            matches: list[IdentityMatchEvidenceDTO] = []
            for match in lookup.matches:
                entry = self.reference_context.register_existing(
                    match.backend_id,
                    object_kind=ReferenceObjectKind.NODE,
                    label=GRAPH_LABEL_BY_NODE_TYPE[match.node.node_type],
                    display_name=node_display_name(match.node),
                    summary=match.node.description,
                    aliases=match.node.aliases,
                )
                selected_refs.append(entry.ref)
                matches.append(
                    IdentityMatchEvidenceDTO(
                        existing_ref=entry.ref,
                        match_kind=match.match_kind,
                        display_name=node_display_name(match.node),
                        aliases=match.node.aliases,
                    )
                )
            evidence.append(
                CandidateIdentityEvidenceDTO(
                    candidate_ref=item.candidate_ref,
                    matches=matches,
                )
            )

        return NodeResolutionStateInputDTO(
            batch=batch,
            identity_evidence=evidence,
            owner=owner,
            references=self.reference_context.entries(self._unique(selected_refs)),
        )

    @staticmethod
    def _unique(refs: list[str]) -> list[str]:
        return list(dict.fromkeys(refs))
