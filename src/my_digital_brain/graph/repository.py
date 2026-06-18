from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from my_digital_brain.graph.models import NeighborhoodResult
from my_digital_brain.graph.repository_core import GraphCoreRepository
from my_digital_brain.graph.repository_memory import GraphMemoryRepository
from my_digital_brain.graph.repository_views import GraphViewRepository

if TYPE_CHECKING:
    from my_digital_brain.storage.graph import GraphClient


class GraphRepository:
    """Stable graph persistence facade.

    The repository is composed from smaller Cypher groups so core writes,
    memory-specific lookups, and view/analytics queries can evolve separately.
    """

    def __init__(self, client: GraphClient) -> None:
        self.client = client
        self.core = GraphCoreRepository(client)
        self.memory = GraphMemoryRepository(client)
        self.views = GraphViewRepository(client)

    def upsert_node(self, label: str, properties: Mapping[str, Any]) -> dict[str, Any]:
        return self.core.upsert_node(label, properties)

    def patch_node(self, node_id: str, properties: Mapping[str, Any]) -> dict[str, Any] | None:
        return self.core.patch_node(node_id, properties)

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return self.core.get_node(node_id)

    def get_relationship(self, relationship_id: str) -> dict[str, Any] | None:
        return self.core.get_relationship(relationship_id)

    def patch_relationship(
        self,
        relationship_id: str,
        properties: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        return self.core.patch_relationship(relationship_id, properties)

    def search_nodes(
        self,
        *,
        label: str | None = None,
        query: str | None = None,
        lifecycle_state: str | None = None,
        privacy_level: str | None = None,
        trust_level: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        return self.core.search_nodes(
            label=label,
            query=query,
            lifecycle_state=lifecycle_state,
            privacy_level=privacy_level,
            trust_level=trust_level,
            limit=limit,
        )

    def upsert_relationship(
        self,
        relationship_type: str,
        from_id: str,
        to_id: str,
        properties: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        return self.core.upsert_relationship(relationship_type, from_id, to_id, properties)

    def get_node_relationships(
        self,
        node_id: str,
        *,
        relationship_type: str | None = None,
        direction: str = "both",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.core.get_node_relationships(
            node_id,
            relationship_type=relationship_type,
            direction=direction,
            limit=limit,
        )

    def get_related_records(
        self,
        node_id: str,
        *,
        depth: int = 1,
        limit: int = 50,
    ) -> NeighborhoodResult:
        return self.core.get_related_records(node_id, depth=depth, limit=limit)

    def get_neighborhood(
        self,
        node_id: str,
        *,
        depth: int = 1,
        limit: int = 50,
    ) -> NeighborhoodResult:
        return self.core.get_neighborhood(node_id, depth=depth, limit=limit)

    def get_relationship_states(
        self,
        context_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.memory.get_relationship_states(context_id, limit=limit)

    def clear_current_relationship_states(
        self,
        context_id: str,
        *,
        except_state_id: str,
        updated_at: str,
    ) -> list[dict[str, Any]]:
        return self.memory.clear_current_relationship_states(
            context_id,
            except_state_id=except_state_id,
            updated_at=updated_at,
        )

    def find_perceptions_for_target(
        self,
        node_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.memory.find_perceptions_for_target(node_id, limit=limit)

    def find_relationship_contexts_for_target(
        self,
        node_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.memory.find_relationship_contexts_for_target(node_id, limit=limit)

    def find_affective_relationships(
        self,
        node_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.memory.find_affective_relationships(node_id, limit=limit)

    def find_change_records_for_target(
        self,
        target_id: str,
        *,
        target_kind: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.memory.find_change_records_for_target(
            target_id,
            target_kind=target_kind,
            limit=limit,
        )

    def find_memory_logs_for_target(
        self,
        target_id: str,
        *,
        from_time: str | None = None,
        to_time: str | None = None,
        log_kind: str | None = None,
        source_kind: str | None = None,
        involved_target_id: str | None = None,
        media_only: bool = False,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.memory.find_memory_logs_for_target(
            target_id,
            from_time=from_time,
            to_time=to_time,
            log_kind=log_kind,
            source_kind=source_kind,
            involved_target_id=involved_target_id,
            media_only=media_only,
            include_archived=include_archived,
            limit=limit,
        )

    def get_memory_log_detail(self, log_id: str, *, limit: int = 50) -> dict[str, Any] | None:
        return self.memory.get_memory_log_detail(log_id, limit=limit)

    def find_sources_for_target(
        self,
        target_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.memory.find_sources_for_target(target_id, limit=limit)

    def find_contradictions(
        self,
        *,
        target_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        contradiction_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.memory.find_contradictions(
            target_id=target_id,
            status=status,
            severity=severity,
            contradiction_type=contradiction_type,
            limit=limit,
        )

    def find_merges(
        self,
        *,
        canonical_node_id: str | None = None,
        merged_node_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.memory.find_merges(
            canonical_node_id=canonical_node_id,
            merged_node_id=merged_node_id,
            status=status,
            limit=limit,
        )

    def find_map_records(
        self,
        *,
        city: str | None = None,
        country: str | None = None,
        limit: int = 100,
    ) -> NeighborhoodResult:
        return self.views.find_map_records(city=city, country=country, limit=limit)

    def count_nodes_by_label(self, *, include_archived: bool = False) -> dict[str, int]:
        return self.views.count_nodes_by_label(include_archived=include_archived)

    def count_relationships_by_type(self) -> dict[str, int]:
        return self.views.count_relationships_by_type()

    def top_connected_nodes(
        self,
        *,
        include_archived: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self.views.top_connected_nodes(include_archived=include_archived, limit=limit)

    def top_emotion_tags(
        self,
        *,
        include_archived: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self.views.top_emotion_tags(include_archived=include_archived, limit=limit)

    def count_unresolved_contradictions(self) -> int:
        return self.views.count_unresolved_contradictions()
