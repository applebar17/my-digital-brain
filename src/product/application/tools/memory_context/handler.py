"""Deterministic MemoryLog and Perception tool handlers."""

from threading import Lock

from product.application.references import ReferenceContext, ReferenceObjectKind
from product.application.tools.memory_context.models import (
    CreateMemoryLogDTO,
    CreatePerceptionDTO,
    MemoryContextObjectKind,
    MemoryContextToolResultDTO,
)
from product.graph import (
    CreatePerceptionPersistenceDTO,
    GraphMemoryService,
    MemoryLogWriteDTO,
    PerceptionDTO,
)


class MemoryContextToolHandler:
    """Resolve local refs, persist typed memory objects, and bind created refs."""

    def __init__(
        self,
        *,
        owner_id: str,
        service: GraphMemoryService,
        reference_context: ReferenceContext,
    ) -> None:
        self.owner_id = owner_id
        self.service = service
        self.reference_context = reference_context
        self._reference_lock = Lock()

    def create_memory_log(
        self,
        request: CreateMemoryLogDTO,
    ) -> MemoryContextToolResultDTO:
        """Create one memory atom after resolving every supplied node reference."""
        primary_host_id = self.reference_context.resolve(
            request.primary_host_ref,
            expected_kind=ReferenceObjectKind.NODE,
        )
        involved_ids = [
            self.reference_context.resolve(ref, expected_kind=ReferenceObjectKind.NODE)
            for ref in request.involved_refs
        ]
        stored = self.service.create_memory_log(
            self.owner_id,
            MemoryLogWriteDTO(
                title=request.title,
                summary=request.summary,
                log_kind=request.log_kind,
                primary_host_backend_id=primary_host_id,
                involved_backend_ids=involved_ids,
                happened_at=request.happened_at,
                time_precision=request.time_precision,
                original_user_words=request.original_user_words,
            ),
        )
        with self._reference_lock:
            entry = self.reference_context.allocate_proposed(
                object_kind=ReferenceObjectKind.MEMORY_LOG,
                label="MemoryLog",
                display_name=request.title,
                summary=request.summary,
            )
            self.reference_context.bind_created(entry.ref, stored.backend_id)
        return MemoryContextToolResultDTO(
            object_kind=MemoryContextObjectKind.MEMORY_LOG,
            object_ref=entry.ref,
            title=request.title,
            summary="Memory log created and linked to its resolved targets.",
        )

    def create_perception(
        self,
        request: CreatePerceptionDTO,
    ) -> MemoryContextToolResultDTO:
        """Create one subjective perception attached to a resolved domain node."""
        target_entry = self.reference_context.entry_for(request.target_ref)
        target_id = self.reference_context.resolve(
            request.target_ref,
            expected_kind=ReferenceObjectKind.NODE,
        )
        stored = self.service.create_perception(
            self.owner_id,
            CreatePerceptionPersistenceDTO(
                target_backend_id=target_id,
                perception=PerceptionDTO(
                    description=request.description,
                    perception_type=request.perception_type,
                    emotional_valence=request.emotional_valence,
                    emotion_tags=request.emotion_tags,
                    original_user_words=request.original_user_words,
                    happened_at=request.happened_at,
                ),
            ),
        )
        target_name = target_entry.display_name or target_entry.label or "target"
        title = f"{request.perception_type.capitalize()}: {target_name}"
        with self._reference_lock:
            entry = self.reference_context.allocate_proposed(
                object_kind=ReferenceObjectKind.CONTEXT,
                label="Perception",
                display_name=title,
                summary=request.description,
            )
            self.reference_context.bind_created(entry.ref, stored.backend_id)
        return MemoryContextToolResultDTO(
            object_kind=MemoryContextObjectKind.PERCEPTION,
            object_ref=entry.ref,
            title=title,
            summary="Perception created and attached to its resolved target.",
        )
