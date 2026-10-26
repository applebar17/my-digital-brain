"""Deterministic handler adapting memory search to model-safe references."""

from product.application.memory_search import (
    MemorySearchFiltersDTO,
    MemorySearchNodeDTO,
    MemorySearchRequestDTO,
    MemorySearchService,
)
from product.application.references import (
    ReferenceContext,
    ReferenceEntryDTO,
    ReferenceObjectKind,
)
from product.application.tools.memory_search.models import (
    MemorySearchObjectDTO,
    MemorySearchToolInputDTO,
    MemorySearchToolRelationshipDTO,
    MemorySearchToolResultDTO,
)

_CONTEXT_LABELS = {
    "Claim",
    "Perception",
    "ProfileMemory",
    "RelationshipContext",
    "RelationshipState",
}


class MemorySearchToolHandler:
    """Resolve model refs, execute owner-scoped search, and project safe results."""

    def __init__(
        self,
        *,
        owner_id: str,
        service: MemorySearchService,
        reference_context: ReferenceContext,
    ) -> None:
        self.owner_id = owner_id
        self.service = service
        self.reference_context = reference_context

    def search_memory(self, request: MemorySearchToolInputDTO) -> MemorySearchToolResultDTO:
        """Execute one read-only search through the invocation's shared reference map.

        Dependencies:
            `MemorySearchService` owns retrieval and bounded hydration.
            `ReferenceContext` resolves incoming refs and registers every returned
            object before this handler constructs the model-facing result.
        """
        internal_request = MemorySearchRequestDTO(
            semantic_query=request.semantic_query,
            filters=MemorySearchFiltersDTO(
                property_query=request.filters.property_query,
                node_labels=list(request.filters.node_labels),
                relationship_types=list(request.filters.relationship_types),
                seed_backend_ids=[self._resolve_seed(ref) for ref in request.filters.seed_refs],
                from_time=request.filters.from_time,
                to_time=request.filters.to_time,
            ),
            neighborhood_depth=request.neighborhood_depth,
            limit=request.limit,
        )
        try:
            result = self.service.search(self.owner_id, internal_request)
        except Exception as error:
            raise ValueError(
                "Memory search could not process the supplied query and filters. Verify "
                "labels, relationship types, date bounds, and active references, then retry."
            ) from error

        entries_by_backend_id: dict[str, ReferenceEntryDTO] = {}
        objects: list[MemorySearchObjectDTO] = []
        for node in result.nodes:
            entry = self._register_node(node)
            entries_by_backend_id[node.backend_id] = entry
            objects.append(
                MemorySearchObjectDTO(
                    **entry.model_dump(),
                    temporal_summary=node.temporal_summary,
                )
            )

        seed_refs = [
            self._required_result_ref(backend_id, entries_by_backend_id)
            for backend_id in result.seed_backend_ids
        ]
        relationships: list[MemorySearchToolRelationshipDTO] = []
        for relationship in result.relationships:
            from_ref = self._required_result_ref(
                relationship.from_backend_id,
                entries_by_backend_id,
            )
            to_ref = self._required_result_ref(
                relationship.to_backend_id,
                entries_by_backend_id,
            )
            entry = self.reference_context.register_existing(
                relationship.backend_id,
                object_kind=ReferenceObjectKind.RELATIONSHIP,
                label=relationship.relationship_type,
                display_name=relationship.relationship_type,
                summary=relationship.summary,
            )
            relationships.append(
                MemorySearchToolRelationshipDTO(
                    **entry.model_dump(),
                    from_ref=from_ref,
                    to_ref=to_ref,
                    temporal_summary=relationship.temporal_summary,
                )
            )

        return MemorySearchToolResultDTO(
            seed_refs=seed_refs,
            objects=objects,
            relationships=relationships,
            truncated=result.truncated,
        )

    def _resolve_seed(self, ref: str) -> str:
        entry = self.reference_context.entry_for(ref)
        if entry.object_kind in {
            ReferenceObjectKind.RELATIONSHIP,
            ReferenceObjectKind.CANDIDATE,
        }:
            raise ValueError(
                f"Reference '{ref}' cannot seed memory search because it represents "
                f"{entry.object_kind.value}. Use an existing graph-object reference."
            )
        return self.reference_context.resolve(ref)

    def _register_node(self, node: MemorySearchNodeDTO) -> ReferenceEntryDTO:
        return self.reference_context.register_existing(
            node.backend_id,
            object_kind=self._object_kind(node.label),
            label=node.label,
            display_name=node.title,
            summary=node.summary,
        )

    def _required_result_ref(
        self,
        backend_id: str,
        entries_by_backend_id: dict[str, ReferenceEntryDTO],
    ) -> str:
        entry = entries_by_backend_id.get(backend_id)
        if entry is not None:
            return entry.ref
        existing_ref = self.reference_context.ref_for_backend_id(backend_id)
        if existing_ref is not None:
            return existing_ref
        raise ValueError(
            "Memory search returned a seed or relationship endpoint without its hydrated "
            "object. The deterministic backend must return coherent endpoints."
        )

    @staticmethod
    def _object_kind(label: str) -> ReferenceObjectKind:
        if label == "MemoryLog":
            return ReferenceObjectKind.MEMORY_LOG
        if label == "MediaAsset":
            return ReferenceObjectKind.MEDIA
        if label in _CONTEXT_LABELS:
            return ReferenceObjectKind.CONTEXT
        return ReferenceObjectKind.NODE
