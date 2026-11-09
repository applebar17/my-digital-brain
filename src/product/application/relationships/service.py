"""Project trusted relationship context detail into model-safe references."""

from product.application.references import (
    ReferenceContext,
    ReferenceEntryDTO,
    ReferenceObjectKind,
)
from product.application.relationships.models import (
    RelationshipContextPacketDTO,
    RelationshipStateProjectionDTO,
)
from product.graph import GraphRelationshipService, RelationshipStateDTO


class RelationshipContextProjectionService:
    """Hydrate bounded context detail without exposing backend identifiers."""

    def __init__(
        self,
        *,
        service: GraphRelationshipService,
        reference_context: ReferenceContext,
        owner_id: str,
    ) -> None:
        self.service = service
        self.reference_context = reference_context
        self.owner_id = owner_id

    def project(
        self,
        context_ref: str,
        *,
        state_limit: int = 10,
    ) -> RelationshipContextPacketDTO:
        """Return one context, its participants, memories, and bounded states."""
        context_entry = self.reference_context.entry_for(context_ref)
        if context_entry.label != "RelationshipContext":
            raise ValueError(f"Reference '{context_ref}' is not a RelationshipContext.")
        detail = self.service.get_context_detail(
            self.owner_id,
            self.reference_context.resolve(
                context_ref,
                expected_kind=ReferenceObjectKind.CONTEXT,
            ),
            state_limit=state_limit,
        )
        participants = [
            self._entry(backend_id, ReferenceObjectKind.NODE, label=None)
            for backend_id in detail.relationship_context.participant_backend_ids
        ]
        memories = [
            self._entry(backend_id, ReferenceObjectKind.MEMORY_LOG, label="MemoryLog")
            for backend_id in detail.relationship_context.memory_log_backend_ids
        ]
        states = [
            RelationshipStateProjectionDTO(
                reference=self._entry(
                    stored.backend_id,
                    ReferenceObjectKind.CONTEXT,
                    label="RelationshipState",
                    display_name=self._state_title(stored.state),
                    summary=stored.state.description or stored.state.emotional_summary,
                ),
                state=stored.state,
            )
            for stored in detail.states
        ]
        return RelationshipContextPacketDTO(
            reference=context_entry,
            context=detail.relationship_context.context,
            participants=participants,
            memory_logs=memories,
            states=states,
        )

    def _entry(
        self,
        backend_id: str,
        object_kind: ReferenceObjectKind,
        *,
        label: str | None,
        display_name: str | None = None,
        summary: str | None = None,
    ) -> ReferenceEntryDTO:
        existing_ref = self.reference_context.ref_for_backend_id(backend_id)
        if existing_ref is not None:
            return self.reference_context.entry_for(existing_ref)
        return self.reference_context.register_existing(
            backend_id,
            object_kind=object_kind,
            label=label,
            display_name=display_name,
            summary=summary,
        )

    @staticmethod
    def _state_title(state: RelationshipStateDTO) -> str:
        meaning = state.status or state.closeness or state.emotional_summary
        return meaning or "Relationship update"
