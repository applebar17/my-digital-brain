"""Deterministic typed operations over the semantic graph repository."""

from product.graph.models import (
    GraphNodeRepository,
    NodeCreate,
    NodePatch,
    StoredNodeDTO,
)


class GraphNodeService:
    """Create and explicitly enrich semantic nodes through one typed repository."""

    def __init__(self, repository: GraphNodeRepository) -> None:
        self.repository = repository

    def create_node(self, owner_id: str, node: NodeCreate) -> StoredNodeDTO:
        """Persist one typed node through the owner-scoped repository."""
        return self.repository.create_node(owner_id, node)

    def update_node(
        self,
        owner_id: str,
        backend_id: str,
        patch: NodePatch,
    ) -> StoredNodeDTO:
        """Apply one explicit subtype patch without clearing unspecified fields.

        Dependencies:
            `GraphNodeRepository` returns the current typed node and persists the
            merged replacement. Alias updates are additive; nullable patch fields
            are omitted rather than interpreted as field deletion.
        """
        current = self.repository.get_node(owner_id, backend_id, patch.node_type)
        updates = patch.model_dump(exclude={"node_type", "aliases_to_add"}, exclude_none=True)
        aliases = list(current.node.aliases)
        for alias in patch.aliases_to_add:
            normalized = alias.strip()
            if normalized and normalized not in aliases:
                aliases.append(normalized)
        updates["aliases"] = aliases
        updated = current.node.model_copy(update=updates)
        return self.repository.update_node(owner_id, backend_id, updated)
