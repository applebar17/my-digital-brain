"""Deterministic dispatch for direct relationships and relationship history."""

from threading import Lock

from product.application.references import ReferenceContext, ReferenceObjectKind
from product.application.tools.relationship_write.models import (
    AppendRelationshipStateActionDTO,
    CreateDirectRelationshipActionDTO,
    CreateOrReuseRelationshipContextActionDTO,
    RelationshipActionRequestDTO,
    RelationshipObjectKind,
    RelationshipToolResultDTO,
    RelationshipWriteOutcome,
    UpdateDirectRelationshipActionDTO,
)
from product.graph import (
    AppendRelationshipStatePersistenceDTO,
    CreateRelationshipContextPersistenceDTO,
    CreateRelationshipPersistenceDTO,
    DirectRelationshipDTO,
    DirectRelationshipPatchDTO,
    GraphRelationshipService,
    RelationshipContextDTO,
    RelationshipStateDTO,
    RelationshipType,
    UpdateRelationshipPersistenceDTO,
)

_ENDPOINT_LABELS: dict[RelationshipType, tuple[set[str], set[str]]] = {
    RelationshipType.PARTICIPATED_IN: ({"Person"}, {"Event"}),
    RelationshipType.HAPPENED_AT: ({"Event"}, {"Place"}),
    RelationshipType.KNOWS: ({"Person"}, {"Person"}),
    RelationshipType.WORKS_AT: ({"Person"}, {"Organization"}),
    RelationshipType.OWNS: ({"Person", "Organization"}, {"Object"}),
    RelationshipType.OWNED_BY: (
        {"Animal", "Object"},
        {"Person", "Organization", "SocialCircle"},
    ),
    RelationshipType.CARED_FOR_BY: ({"Animal"}, {"Person", "Organization"}),
    RelationshipType.LIVES_WITH: (
        {"Person", "Animal"},
        {"Person", "Animal", "Organization", "SocialCircle"},
    ),
    RelationshipType.MEMBER_OF: ({"Person", "Animal"}, {"SocialCircle"}),
    RelationshipType.LOCATED_IN: ({"Place"}, {"Place"}),
}


class RelationshipToolHandler:
    """Resolve model refs and dispatch one typed relationship persistence action."""

    def __init__(
        self,
        *,
        owner_id: str,
        service: GraphRelationshipService,
        reference_context: ReferenceContext,
    ) -> None:
        self.owner_id = owner_id
        self.service = service
        self.reference_context = reference_context
        self._reference_lock = Lock()

    def execute(self, request: RelationshipActionRequestDTO) -> RelationshipToolResultDTO:
        """Dispatch the discriminated action after validating its reference semantics."""
        action = request.action
        if isinstance(action, CreateDirectRelationshipActionDTO):
            return self._create_direct(action)
        if isinstance(action, UpdateDirectRelationshipActionDTO):
            return self._update_direct(action)
        if isinstance(action, CreateOrReuseRelationshipContextActionDTO):
            return self._create_or_reuse_context(action)
        return self._append_state(action)

    def _create_direct(
        self,
        action: CreateDirectRelationshipActionDTO,
    ) -> RelationshipToolResultDTO:
        from_entry = self.reference_context.entry_for(action.from_ref)
        to_entry = self.reference_context.entry_for(action.to_ref)
        self._validate_endpoints(action.relationship_type, from_entry.label, to_entry.label)
        stored = self.service.create_or_get_relationship(
            self.owner_id,
            CreateRelationshipPersistenceDTO(
                from_backend_id=self.reference_context.resolve(
                    action.from_ref,
                    expected_kind=ReferenceObjectKind.NODE,
                ),
                to_backend_id=self.reference_context.resolve(
                    action.to_ref,
                    expected_kind=ReferenceObjectKind.NODE,
                ),
                relationship=DirectRelationshipDTO(
                    relationship_type=action.relationship_type,
                    description=action.description,
                    relationship_detail=action.relationship_detail,
                    valid_from=action.valid_from,
                    valid_to=action.valid_to,
                    original_user_words=action.original_user_words,
                ),
            ),
        )
        title = self._direct_title(
            action.relationship_type,
            from_entry.display_name,
            to_entry.display_name,
        )
        ref = self._bind_result(
            backend_id=stored.backend_id,
            created=stored.created,
            object_kind=ReferenceObjectKind.RELATIONSHIP,
            label=action.relationship_type.value,
            display_name=title,
            summary=stored.relationship.description,
        )
        return RelationshipToolResultDTO(
            object_kind=RelationshipObjectKind.DIRECT_RELATIONSHIP,
            outcome=(
                RelationshipWriteOutcome.CREATED
                if stored.created
                else RelationshipWriteOutcome.REUSED
            ),
            object_ref=ref,
            title=title,
            summary=(
                "Direct relationship created."
                if stored.created
                else "Direct relationship reused."
            ),
        )

    def _update_direct(
        self,
        action: UpdateDirectRelationshipActionDTO,
    ) -> RelationshipToolResultDTO:
        backend_id = self.reference_context.resolve(
            action.relationship_ref,
            expected_kind=ReferenceObjectKind.RELATIONSHIP,
        )
        stored = self.service.update_relationship(
            self.owner_id,
            UpdateRelationshipPersistenceDTO(
                relationship_backend_id=backend_id,
                patch=DirectRelationshipPatchDTO(
                    description=action.description,
                    relationship_detail=action.relationship_detail,
                    valid_from=action.valid_from,
                    valid_to=action.valid_to,
                    original_user_words=action.original_user_words,
                ),
            ),
        )
        with self._reference_lock:
            entry = self.reference_context.entry_for(action.relationship_ref)
            self.reference_context.refresh_existing(
                action.relationship_ref,
                display_name=entry.display_name,
                summary=stored.relationship.description,
                aliases=[],
            )
        return RelationshipToolResultDTO(
            object_kind=RelationshipObjectKind.DIRECT_RELATIONSHIP,
            outcome=RelationshipWriteOutcome.UPDATED,
            object_ref=action.relationship_ref,
            title=entry.display_name or stored.relationship.relationship_type.value,
            summary="Direct relationship explicitly updated.",
        )

    def _create_or_reuse_context(
        self,
        action: CreateOrReuseRelationshipContextActionDTO,
    ) -> RelationshipToolResultDTO:
        participant_entries = [
            self.reference_context.entry_for(ref) for ref in action.participant_refs
        ]
        participant_ids = [
            self.reference_context.resolve(ref, expected_kind=ReferenceObjectKind.NODE)
            for ref in action.participant_refs
        ]
        memory_ids = self._resolve_memory_refs(action.memory_refs)
        stored = self.service.create_or_get_context(
            self.owner_id,
            CreateRelationshipContextPersistenceDTO(
                participant_backend_ids=participant_ids,
                memory_log_backend_ids=memory_ids,
                context=RelationshipContextDTO(
                    category=action.category,
                    description=action.description,
                    relationship_kind=action.relationship_kind,
                    original_user_words=action.original_user_words,
                ),
            ),
        )
        names = [
            entry.display_name or entry.label or "participant"
            for entry in participant_entries
        ]
        title = f"{action.category.value.capitalize()}: {' & '.join(names)}"
        ref = self._bind_result(
            backend_id=stored.backend_id,
            created=stored.created,
            object_kind=ReferenceObjectKind.CONTEXT,
            label="RelationshipContext",
            display_name=title,
            summary=stored.context.description,
        )
        return RelationshipToolResultDTO(
            object_kind=RelationshipObjectKind.RELATIONSHIP_CONTEXT,
            outcome=(
                RelationshipWriteOutcome.CREATED
                if stored.created
                else RelationshipWriteOutcome.REUSED
            ),
            object_ref=ref,
            title=title,
            summary=(
                "Relationship context created."
                if stored.created
                else "Relationship context reused."
            ),
        )

    def _append_state(
        self,
        action: AppendRelationshipStateActionDTO,
    ) -> RelationshipToolResultDTO:
        context_entry = self.reference_context.entry_for(action.context_ref)
        if context_entry.label != "RelationshipContext":
            raise ValueError(
                f"Reference '{action.context_ref}' is not a RelationshipContext. "
                "Create or reuse the context before appending a state."
            )
        stored = self.service.append_state(
            self.owner_id,
            AppendRelationshipStatePersistenceDTO(
                context_backend_id=self.reference_context.resolve(
                    action.context_ref,
                    expected_kind=ReferenceObjectKind.CONTEXT,
                ),
                memory_log_backend_ids=self._resolve_memory_refs(action.memory_refs),
                state=RelationshipStateDTO(
                    status=action.status,
                    closeness=action.closeness,
                    description=action.description,
                    emotional_summary=action.emotional_summary,
                    emotional_valence=action.emotional_valence,
                    emotion_tags=action.emotion_tags,
                    original_user_words=action.original_user_words,
                    valid_from=action.valid_from,
                    valid_to=action.valid_to,
                    time_precision=action.time_precision,
                ),
            ),
        )
        state_title = self._state_title(stored.state)
        ref = self._bind_result(
            backend_id=stored.backend_id,
            created=stored.created,
            object_kind=ReferenceObjectKind.CONTEXT,
            label="RelationshipState",
            display_name=state_title,
            summary=stored.state.description or stored.state.emotional_summary,
        )
        return RelationshipToolResultDTO(
            object_kind=RelationshipObjectKind.RELATIONSHIP_STATE,
            outcome=(
                RelationshipWriteOutcome.CREATED
                if stored.created
                else RelationshipWriteOutcome.REUSED
            ),
            object_ref=ref,
            title=state_title,
            summary=(
                "Relationship state appended."
                if stored.created
                else "Identical relationship state reused."
            ),
        )

    def _resolve_memory_refs(self, refs: list[str]) -> list[str]:
        return [
            self.reference_context.resolve(
                ref,
                expected_kind=ReferenceObjectKind.MEMORY_LOG,
            )
            for ref in refs
        ]

    def _bind_result(
        self,
        *,
        backend_id: str,
        created: bool,
        object_kind: ReferenceObjectKind,
        label: str,
        display_name: str,
        summary: str | None,
    ) -> str:
        with self._reference_lock:
            if created:
                entry = self.reference_context.allocate_proposed(
                    object_kind=object_kind,
                    label=label,
                    display_name=display_name,
                    summary=summary,
                )
                self.reference_context.bind_created(entry.ref, backend_id)
                return entry.ref
            return self.reference_context.register_existing(
                backend_id,
                object_kind=object_kind,
                label=label,
                display_name=display_name,
                summary=summary,
            ).ref

    @staticmethod
    def _validate_endpoints(
        relationship_type: RelationshipType,
        from_label: str | None,
        to_label: str | None,
    ) -> None:
        if relationship_type == RelationshipType.RELATED_TO:
            return
        allowed_from, allowed_to = _ENDPOINT_LABELS[relationship_type]
        if from_label not in allowed_from or to_label not in allowed_to:
            raise ValueError(
                f"{relationship_type.value} requires source labels {sorted(allowed_from)} "
                f"and target labels {sorted(allowed_to)}, but received "
                f"{from_label or 'unknown'} -> {to_label or 'unknown'}."
            )

    @staticmethod
    def _direct_title(
        relationship_type: RelationshipType,
        from_name: str | None,
        to_name: str | None,
    ) -> str:
        return f"{from_name or 'Object'} {relationship_type.value} {to_name or 'object'}"

    @staticmethod
    def _state_title(state: RelationshipStateDTO) -> str:
        meaning = (
            state.status
            or state.closeness
            or state.emotional_summary
            or "Relationship update"
        )
        timing = state.valid_from or state.valid_to
        return f"{meaning} ({timing})" if timing else meaning
