"""Application-facing service for memory logs and perceptions."""

from product.graph.memory.models import (
    CreatePerceptionPersistenceDTO,
    GraphMemoryRepository,
    MemoryLogWriteDTO,
    StoredMemoryLogDTO,
    StoredPerceptionDTO,
)


class GraphMemoryService:
    """Persist typed memory objects without exposing storage mechanics to tools."""

    def __init__(self, repository: GraphMemoryRepository) -> None:
        self.repository = repository

    def create_memory_log(
        self,
        owner_id: str,
        memory_log: MemoryLogWriteDTO,
    ) -> StoredMemoryLogDTO:
        """Create one additive memory atom after all target IDs are resolved."""
        return self.repository.create_memory_log(owner_id, memory_log)

    def create_perception(
        self,
        owner_id: str,
        request: CreatePerceptionPersistenceDTO,
    ) -> StoredPerceptionDTO:
        """Create one subjective perception attached to an existing target."""
        return self.repository.create_perception(owner_id, request)
