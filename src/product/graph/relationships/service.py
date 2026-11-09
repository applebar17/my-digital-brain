"""Application-facing relationship persistence and read service."""

from product.graph.relationships.models import (
    AppendRelationshipStatePersistenceDTO,
    CreateRelationshipContextPersistenceDTO,
    CreateRelationshipPersistenceDTO,
    GraphRelationshipRepository,
    RelationshipContextDetailDTO,
    StoredDirectRelationshipDTO,
    StoredRelationshipContextDTO,
    StoredRelationshipStateDTO,
    UpdateRelationshipPersistenceDTO,
)


class GraphRelationshipService:
    """Expose typed relationship operations independently of graph mechanics."""

    def __init__(self, repository: GraphRelationshipRepository) -> None:
        self.repository = repository

    def create_or_get_relationship(
        self,
        owner_id: str,
        request: CreateRelationshipPersistenceDTO,
    ) -> StoredDirectRelationshipDTO:
        """Create a direct edge or return the exact existing type/endpoints edge."""
        return self.repository.create_or_get_relationship(owner_id, request)

    def update_relationship(
        self,
        owner_id: str,
        request: UpdateRelationshipPersistenceDTO,
    ) -> StoredDirectRelationshipDTO:
        """Apply one explicit non-destructive direct-edge patch."""
        return self.repository.update_relationship(owner_id, request)

    def create_or_get_context(
        self,
        owner_id: str,
        request: CreateRelationshipContextPersistenceDTO,
    ) -> StoredRelationshipContextDTO:
        """Create or reuse an exact owner/participants/category context."""
        return self.repository.create_or_get_context(owner_id, request)

    def append_state(
        self,
        owner_id: str,
        request: AppendRelationshipStatePersistenceDTO,
    ) -> StoredRelationshipStateDTO:
        """Append a meaningful state or return its exact existing observation."""
        return self.repository.append_state(owner_id, request)

    def get_context_detail(
        self,
        owner_id: str,
        context_backend_id: str,
        *,
        state_limit: int = 10,
    ) -> RelationshipContextDetailDTO:
        """Read one context with bounded newest-first state history."""
        if state_limit < 1:
            raise ValueError("state_limit must be at least 1.")
        return self.repository.get_context_detail(
            owner_id,
            context_backend_id,
            state_limit=state_limit,
        )
