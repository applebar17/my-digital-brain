"""Deterministic graph-action dispatch with coherent workflow references."""

from threading import Lock

from pydantic import BaseModel

from product.application.references import (
    ReferenceContext,
    ReferenceObjectKind,
    ReferenceResolutionStatus,
)
from product.application.tools.graph_action.models import (
    GraphActionBaseDTO,
    GraphActionResultDTO,
    UpdateActionBaseDTO,
)
from product.graph import GRAPH_LABEL_BY_NODE_TYPE, GraphNodeService
from product.graph.presentation import node_display_name


class GraphActionToolHandler:
    """Create or update typed nodes while keeping backend IDs private."""

    def __init__(
        self,
        *,
        owner_id: str,
        service: GraphNodeService,
        reference_context: ReferenceContext,
        candidate_types: dict[str, str],
    ) -> None:
        self.owner_id = owner_id
        self.service = service
        self.reference_context = reference_context
        self.candidate_types = candidate_types
        self._new_ref_by_candidate: dict[str, str] = {}
        self._creating_candidates: set[str] = set()
        self._reference_lock = Lock()
        self._update_lock = Lock()

    def execute(self, request: BaseModel) -> GraphActionResultDTO:
        """Dispatch one validated action and return its model-facing reference.

        Dependencies:
            `GraphNodeService` owns typed persistence. `ReferenceContext` validates
            candidate/target refs and binds successful backend creations. Reference
            mutation is serialized while independent database writes may run in parallel.
        """
        action = getattr(request, "action", None)
        if not isinstance(action, GraphActionBaseDTO):
            raise ValueError("Graph action request did not contain a supported typed action.")
        self._validate_candidate(action)
        if isinstance(action, UpdateActionBaseDTO):
            return self._update(action)
        return self._create(action)

    def _create(self, action: GraphActionBaseDTO) -> GraphActionResultDTO:
        node = action.node
        with self._reference_lock:
            node_ref = self._new_ref_by_candidate.get(action.candidate_ref)
            if node_ref is None:
                entry = self.reference_context.allocate_proposed(
                    object_kind=ReferenceObjectKind.NODE,
                    label=GRAPH_LABEL_BY_NODE_TYPE[node.node_type],
                    display_name=node_display_name(node),
                    summary=node.description,
                    aliases=node.aliases,
                )
                node_ref = entry.ref
                self._new_ref_by_candidate[action.candidate_ref] = node_ref
            elif (
                self.reference_context.entry_for(node_ref).resolution_status
                == ReferenceResolutionStatus.CREATED
            ):
                raise ValueError(
                    f"Candidate '{action.candidate_ref}' was already created as "
                    f"'{node_ref}'. Reuse that node reference instead of creating it again."
                )
            if action.candidate_ref in self._creating_candidates:
                raise ValueError(
                    f"Candidate '{action.candidate_ref}' already has a create action in progress."
                )
            self._creating_candidates.add(action.candidate_ref)

        try:
            stored = self.service.create_node(self.owner_id, node)
            with self._reference_lock:
                self.reference_context.bind_created(node_ref, stored.backend_id)
        finally:
            with self._reference_lock:
                self._creating_candidates.discard(action.candidate_ref)
        return GraphActionResultDTO(
            candidate_ref=action.candidate_ref,
            operation="create",
            node_type=node.node_type,
            node_ref=node_ref,
            display_name=node_display_name(stored.node),
            changed_fields=list(
                node.model_dump(exclude={"node_type"}, exclude_none=True).keys()
            ),
        )

    def _update(self, action: UpdateActionBaseDTO) -> GraphActionResultDTO:
        patch = action.patch
        target_entry = self.reference_context.entry_for(action.target_ref)
        if target_entry.object_kind != ReferenceObjectKind.NODE:
            raise ValueError(
                f"Reference '{action.target_ref}' is not an existing semantic node."
            )
        backend_id = self.reference_context.resolve(
            action.target_ref,
            expected_kind=ReferenceObjectKind.NODE,
        )
        with self._update_lock:
            stored = self.service.update_node(self.owner_id, backend_id, patch)
            with self._reference_lock:
                self.reference_context.refresh_existing(
                    action.target_ref,
                    display_name=node_display_name(stored.node),
                    summary=stored.node.description,
                    aliases=stored.node.aliases,
                )
        changed_fields = list(
            patch.model_dump(
                exclude={"node_type", "aliases_to_add"},
                exclude_none=True,
            ).keys()
        )
        if patch.aliases_to_add:
            changed_fields.append("aliases")
        return GraphActionResultDTO(
            candidate_ref=action.candidate_ref,
            operation="update",
            node_type=patch.node_type,
            node_ref=action.target_ref,
            display_name=node_display_name(stored.node),
            changed_fields=changed_fields,
        )

    def _validate_candidate(self, action: GraphActionBaseDTO) -> None:
        candidate_entry = self.reference_context.entry_for(action.candidate_ref)
        if candidate_entry.object_kind != ReferenceObjectKind.CANDIDATE:
            raise ValueError(
                f"Reference '{action.candidate_ref}' does not identify a node candidate."
            )
        expected_label = self.candidate_types.get(action.candidate_ref)
        supplied_label = GRAPH_LABEL_BY_NODE_TYPE[action.node_type]
        if expected_label is None:
            raise ValueError(
                f"Candidate reference '{action.candidate_ref}' is not part of this batch."
            )
        if expected_label != supplied_label:
            raise ValueError(
                f"Candidate '{action.candidate_ref}' requires {expected_label}, not "
                f"{supplied_label}. Use the matching typed action variant."
            )
