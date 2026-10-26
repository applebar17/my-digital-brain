"""Deterministic orchestration over existing semantic and graph retrieval behavior."""

from product.application.memory_search.models import (
    MemorySearchBackend,
    MemorySearchRequestDTO,
    MemorySearchResultDTO,
    MemorySearchSeedDTO,
)


class MemorySearchService:
    """Unify semantic and deterministic seed selection before bounded hydration."""

    def __init__(self, backend: MemorySearchBackend) -> None:
        self.backend = backend

    def search(
        self,
        owner_id: str,
        request: MemorySearchRequestDTO,
    ) -> MemorySearchResultDTO:
        """Select graph seeds and hydrate them through the configured backend.

        Dependencies:
            `MemorySearchBackend` adapts the existing semantic search and graph
            query services. This class only coordinates those capabilities and
            does not implement ranking, vector search, or graph traversal.
        """
        seeds: list[MemorySearchSeedDTO] = []
        if request.semantic_query is not None:
            seeds.extend(
                self.backend.semantic_seeds(
                    owner_id,
                    request.semantic_query,
                    filters=request.filters,
                    limit=request.limit,
                )
            )
        if request.filters.has_seed_selector():
            seeds.extend(
                self.backend.deterministic_seeds(
                    owner_id,
                    request.filters,
                    limit=request.limit,
                )
            )

        seed_backend_ids = self._unique_seed_ids(seeds, limit=request.limit)
        if not seed_backend_ids:
            return MemorySearchResultDTO()
        return self.backend.hydrate(
            owner_id,
            seed_backend_ids,
            filters=request.filters,
            depth=request.neighborhood_depth,
            limit=request.limit,
        )

    @staticmethod
    def _unique_seed_ids(seeds: list[MemorySearchSeedDTO], *, limit: int) -> list[str]:
        """Preserve provider ranking while removing repeated backend objects."""
        unique: list[str] = []
        seen: set[str] = set()
        for seed in seeds:
            if seed.backend_id not in seen:
                seen.add(seed.backend_id)
                unique.append(seed.backend_id)
            if len(unique) >= limit:
                break
        return unique
