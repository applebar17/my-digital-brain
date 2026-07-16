from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from my_digital_brain.config import Settings
from my_digital_brain.graph.constants import OWNER_ALIAS
from my_digital_brain.graph.exceptions import GraphConflictError, GraphValidationError
from my_digital_brain.graph.models import PersonNode
from my_digital_brain.graph.repository import GraphRepository


class OwnerNodeManager:
    """Trusted backend lifecycle manager for the canonical graph owner."""

    def __init__(self, repository: GraphRepository, settings: Settings) -> None:
        self.repository = repository
        self.owner_node_id = settings.owner_graph_node_id

    def ensure_owner(self) -> dict[str, Any]:
        owner_nodes = self.repository.find_owner_nodes()
        configured = self.repository.get_node(self.owner_node_id)

        if configured is None:
            if owner_nodes:
                raise GraphConflictError(
                    "Graph already contains an owner with a different configured node id"
                )
            return self._create_owner()

        if configured["label"] != PersonNode.label:
            raise GraphConflictError(
                f"Configured owner node id is already used by {configured['label']}"
            )
        if configured["properties"].get("is_owner") is not True:
            raise GraphConflictError(
                "Configured owner node exists but is_owner is not true; explicit repair is required"
            )
        if any(node["properties"].get("id") != self.owner_node_id for node in owner_nodes):
            raise GraphConflictError("Graph contains multiple owner Person nodes")
        return configured

    def validate_owner_integrity(self) -> dict[str, Any]:
        return self.ensure_owner()

    def resolve_owner_alias(self, alias: str) -> str:
        if alias != OWNER_ALIAS:
            raise GraphValidationError(f"Unsupported owner alias: {alias}")
        return self.owner_node_id

    def _create_owner(self) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        properties = PersonNode(
            id=self.owner_node_id,
            is_owner=True,
            status="active",
            created_at=now,
            updated_at=now,
        ).model_dump(mode="python", exclude_none=True)
        return self.repository.upsert_node(PersonNode.label, properties)
