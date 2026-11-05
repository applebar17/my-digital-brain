"""Deterministic identity evidence for typed semantic node candidates."""

import re
import unicodedata

from product.graph.models import (
    GraphNodeRepository,
    IdentityLookupResultDTO,
    IdentityMatchDTO,
    IdentityMatchKind,
    NodeCreate,
    StoredNodeDTO,
)
from product.graph.presentation import node_display_name


class GraphIdentityLookupService:
    """Find bounded same-type identity evidence without deciding node identity."""

    def __init__(self, repository: GraphNodeRepository, *, maximum_matches: int = 5) -> None:
        if maximum_matches < 1:
            raise ValueError("maximum_matches must be at least 1.")
        self.repository = repository
        self.maximum_matches = maximum_matches

    def lookup(self, owner_id: str, candidate: NodeCreate) -> IdentityLookupResultDTO:
        """Search and classify existing nodes using names and aliases only.

        Dependencies:
            `GraphNodeRepository` performs the bounded owner-scoped graph search.
            This service classifies evidence but never binds, merges, creates, or
            rejects an identity.
        """
        terms = self._identity_terms(candidate)
        records = self.repository.search_nodes(
            owner_id,
            candidate.node_type,
            terms,
            limit=max(self.maximum_matches * 5, self.maximum_matches),
        )
        matches = [
            IdentityMatchDTO(
                backend_id=record.backend_id,
                node=record.node,
                match_kind=match_kind,
            )
            for record in records
            if (match_kind := self._match_kind(candidate, record)) is not None
        ]
        matches.sort(key=lambda match: self._priority(match.match_kind))
        return IdentityLookupResultDTO(matches=matches[: self.maximum_matches])

    @staticmethod
    def _identity_terms(node: NodeCreate) -> list[str]:
        return GraphIdentityLookupService._unique([node_display_name(node), *node.aliases])

    @staticmethod
    def _match_kind(
        candidate: NodeCreate,
        existing: StoredNodeDTO,
    ) -> IdentityMatchKind | None:
        candidate_name = GraphIdentityLookupService._normalize(node_display_name(candidate))
        existing_name = GraphIdentityLookupService._normalize(node_display_name(existing.node))
        candidate_aliases = {
            GraphIdentityLookupService._normalize(alias) for alias in candidate.aliases
        }
        existing_aliases = {
            GraphIdentityLookupService._normalize(alias) for alias in existing.node.aliases
        }
        if candidate_name == existing_name:
            return IdentityMatchKind.EXACT_NAME
        if (
            candidate_name in existing_aliases
            or existing_name in candidate_aliases
            or bool(candidate_aliases & existing_aliases)
        ):
            return IdentityMatchKind.EXACT_ALIAS
        candidate_tokens = set(candidate_name.split())
        existing_tokens = set(existing_name.split())
        if len(candidate_tokens) == 1 and candidate_tokens <= existing_tokens:
            return IdentityMatchKind.NAME_TOKEN
        return None

    @staticmethod
    def _priority(match_kind: IdentityMatchKind) -> int:
        return {
            IdentityMatchKind.EXACT_NAME: 0,
            IdentityMatchKind.EXACT_ALIAS: 1,
            IdentityMatchKind.NAME_TOKEN: 2,
        }[match_kind]

    @staticmethod
    def _normalize(value: str) -> str:
        ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        return re.sub(r"\s+", " ", ascii_value.casefold()).strip()

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            key = GraphIdentityLookupService._normalize(normalized)
            if key and key not in seen:
                seen.add(key)
                result.append(normalized)
        return result
