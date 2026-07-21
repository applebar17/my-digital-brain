from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from my_digital_brain.ai.logging import log_event
from my_digital_brain.graph.models import NodeSearchResult
from my_digital_brain.graph.utils import normalize_text
from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    EntityLookupCandidate,
    EntityLookupContextPacket,
    EntityLookupRelatedContext,
    EntityLookupRequest,
    EntityLookupResult,
    IdentityLookupStatus,
    IdentityMatchKind,
    PlannedEntityRefDraft,
    ReferenceObjectKind,
)
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry


class IdentityLookupError(RuntimeError):
    """Raised when deterministic lookup cannot safely complete."""


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DeterministicIdentityLookupService:
    """Find bounded, label-constrained identity candidates before extraction."""

    graph_service: Any
    owner_manager: Any | None = None
    owner_graph_node_id: str | None = None
    max_candidates: int = 5

    def lookup(
        self,
        request: EntityLookupRequest,
        *,
        registry: RunReferenceRegistry,
    ) -> EntityLookupResult:
        log_event(
            logger,
            "ingestion.identity_lookup.request",
            component="ingestion",
            candidate_ref=request.candidate_ref,
            entity_type=request.entity_type,
            max_candidates=request.max_candidates,
        )
        nodes = self._search(request)
        matched: dict[str, tuple[NodeSearchResult, IdentityMatchKind]] = {}
        for node in nodes:
            node_id = node.properties.get("id")
            if not node_id or self._is_owner(node_id):
                continue
            match_kind = match_node_identity(node, request)
            if match_kind is not None:
                current = matched.get(str(node_id))
                if current is None or _match_priority(match_kind) < _match_priority(current[1]):
                    matched[str(node_id)] = (node, match_kind)

        candidates = [
            self._candidate(node, match_kind, registry)
            for node, match_kind in sorted(
                matched.values(),
                key=lambda item: (
                    _match_priority(item[1]),
                    _display_name(item[0]).casefold(),
                    str(item[0].properties.get("id")),
                ),
            )[: request.max_candidates]
        ]
        if candidates:
            status = (
                IdentityLookupStatus.ONE_CANDIDATE
                if len(candidates) == 1
                else IdentityLookupStatus.MULTIPLE_CANDIDATES
            )
            result = EntityLookupResult(
                candidate_ref=request.candidate_ref,
                status=status,
                candidates=candidates,
                guidance=_guidance(status),
            )
            self._log_result(result)
            return result

        fuzzy_candidates = self._fuzzy_candidates(request, registry)
        if fuzzy_candidates:
            result = EntityLookupResult(
                candidate_ref=request.candidate_ref,
                status=IdentityLookupStatus.FUZZY_CANDIDATES_ONLY,
                candidates=fuzzy_candidates[: request.max_candidates],
                guidance=_guidance(IdentityLookupStatus.FUZZY_CANDIDATES_ONLY),
            )
            self._log_result(result)
            return result
        result = EntityLookupResult(
            candidate_ref=request.candidate_ref,
            status=IdentityLookupStatus.NO_CANDIDATES,
            guidance=_guidance(IdentityLookupStatus.NO_CANDIDATES),
        )
        self._log_result(result)
        return result

    @staticmethod
    def _log_result(result: EntityLookupResult) -> None:
        log_event(
            logger,
            "ingestion.identity_lookup.classified",
            component="ingestion",
            candidate_ref=result.candidate_ref,
            status=str(result.status),
            candidate_count=len(result.candidates),
        )

    def lookup_planned_entity(
        self,
        planned: PlannedEntityRefDraft,
        *,
        registry: RunReferenceRegistry,
    ) -> EntityLookupContextPacket:
        request = request_from_planned_entity(planned, max_candidates=self.max_candidates)
        result = self.lookup(request, registry=registry)
        return EntityLookupContextPacket(
            candidate_ref=planned.local_ref,
            entity_type=request.entity_type,
            proposed_display_name=request.display_name,
            proposed_aliases=list(request.aliases),
            lookup=result,
            guidance=result.guidance,
        )

    def lookup_plan(
        self,
        plan: Any,
        *,
        registry: RunReferenceRegistry,
    ) -> list[EntityLookupContextPacket]:
        packets: list[EntityLookupContextPacket] = []
        for action in plan.actions:
            for planned in action.entities:
                if planned.suggested_entity_type is None:
                    continue
                packets.append(self.lookup_planned_entity(planned, registry=registry))
        return packets

    def _search(self, request: EntityLookupRequest) -> list[NodeSearchResult]:
        terms = _request_terms(request)
        if not terms:
            return []
        nodes: dict[str, NodeSearchResult] = {}
        try:
            for term in terms:
                results = self.graph_service.search_nodes(
                    label=request.entity_type,
                    query=term,
                    limit=max(request.max_candidates * 10, 25),
                )
                for raw_node in results or []:
                    node = NodeSearchResult.model_validate(raw_node)
                    if _is_active(node):
                        node_id = node.properties.get("id")
                        if node_id:
                            nodes[str(node_id)] = node
        except Exception as exc:
            raise IdentityLookupError("Deterministic identity lookup failed.") from exc
        return list(nodes.values())

    def _fuzzy_candidates(
        self,
        request: EntityLookupRequest,
        registry: RunReferenceRegistry,
    ) -> list[EntityLookupCandidate]:
        fuzzy_search = getattr(self.graph_service, "search_identity_fuzzy", None)
        if fuzzy_search is None:
            return []
        try:
            raw_nodes = fuzzy_search(request, limit=request.max_candidates)
            candidates: list[EntityLookupCandidate] = []
            for raw_node in raw_nodes or []:
                node = NodeSearchResult.model_validate(raw_node)
                node_id = node.properties.get("id")
                if not node_id or self._is_owner(node_id) or not _is_active(node):
                    continue
                ref = registry.register_existing(
                    str(node_id),
                    object_kind=ReferenceObjectKind.NODE,
                    label=node.label,
                    display_label=_display_name(node),
                    aliases=_aliases(node),
                )
                candidates.append(
                    EntityLookupCandidate(
                        ref=ref,
                        label=node.label,
                        display_name=_display_name(node),
                        aliases=_aliases(node),
                        match_kind=IdentityMatchKind.FUZZY_HINT,
                        match_score=_score(node),
                        related_context=EntityLookupRelatedContext(),
                    ),
                )
            return candidates
        except Exception as exc:
            raise IdentityLookupError("Fuzzy identity lookup failed.") from exc

    def _candidate(
        self,
        node: NodeSearchResult,
        match_kind: IdentityMatchKind,
        registry: RunReferenceRegistry,
    ) -> EntityLookupCandidate:
        ref = registry.register_existing(
            str(node.properties["id"]),
            object_kind=ReferenceObjectKind.NODE,
            label=node.label,
            display_label=_display_name(node),
            aliases=_aliases(node),
        )
        return EntityLookupCandidate(
            ref=ref,
            label=node.label,
            display_name=_display_name(node),
            aliases=_aliases(node),
            match_kind=match_kind,
            match_score=1.0 if match_kind != IdentityMatchKind.NAME_TOKEN else 0.8,
            related_context=EntityLookupRelatedContext(),
        )

    def _is_owner(self, node_id: Any) -> bool:
        owner_id = self.owner_graph_node_id
        if self.owner_manager is not None:
            owner_id = self.owner_manager.resolve_owner_alias("OWNER")
        return owner_id is not None and str(node_id) == str(owner_id)


def request_from_planned_entity(
    planned: PlannedEntityRefDraft,
    *,
    max_candidates: int = 5,
) -> EntityLookupRequest:
    entity_type = planned.suggested_entity_type
    if entity_type is None:
        raise ValueError("A planned entity must have a suggested type before lookup.")
    return EntityLookupRequest(
        candidate_ref=planned.local_ref,
        entity_type=getattr(entity_type, "value", str(entity_type)),
        display_name=planned.mention_text,
        aliases=list(planned.aliases),
        max_candidates=max_candidates,
    )


def request_from_candidate(
    candidate: CandidateEntity,
    *,
    max_candidates: int = 5,
) -> EntityLookupRequest:
    typed = candidate.typed_properties
    identity_values = {
        key: _string_values(typed.get(key))
        for key in ("name", "title", "normalized_name")
        if _string_values(typed.get(key))
    }
    return EntityLookupRequest(
        candidate_ref=candidate.local_ref,
        entity_type=candidate.entity_type,
        display_name=candidate.display_name,
        aliases=list(candidate.aliases),
        typed_identity_values=identity_values,
        max_candidates=max_candidates,
    )


def match_node_identity(
    node: NodeSearchResult,
    request: EntityLookupRequest,
    *,
    include_tokens: bool = True,
) -> IdentityMatchKind | None:
    display_terms = {_normalize(term) for term in _string_values(request.display_name)}
    display_terms.update(_normalize(term) for term in request.typed_identity_values.get("name", []))
    alias_terms = {_normalize(term) for term in request.aliases}
    alias_terms.update(_normalize(term) for term in request.typed_identity_values.get("title", []))
    exact_name_values = _string_values(
        [
            node.properties.get(field)
            for field in ("display_name", "name", "normalized_name", "title")
        ],
    )
    node_aliases = {_normalize(value) for value in _aliases(node)}
    normalized_names = {_normalize(value) for value in exact_name_values}
    if display_terms & normalized_names:
        return IdentityMatchKind.EXACT_NAME
    if display_terms & node_aliases or alias_terms & normalized_names or alias_terms & node_aliases:
        return IdentityMatchKind.EXACT_ALIAS
    if not include_tokens:
        return None
    for term in display_terms:
        if _token_match(term, exact_name_values):
            return IdentityMatchKind.NAME_TOKEN
    return None


def _request_terms(request: EntityLookupRequest) -> list[str]:
    values = [request.display_name, *request.aliases]
    for typed_values in request.typed_identity_values.values():
        values.extend(typed_values)
    return _unique_text(values)


def _token_match(term: str, values: list[str]) -> bool:
    requested = set(term.split())
    return bool(requested) and len(requested) == 1 and any(
        requested <= set(_normalize(value).split()) for value in values
    )


def _display_name(node: NodeSearchResult) -> str | None:
    for field in ("display_name", "name", "title", "description"):
        value = node.properties.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _aliases(node: NodeSearchResult) -> list[str]:
    return _string_values(node.properties.get("aliases"))


def _is_active(node: NodeSearchResult) -> bool:
    return str(node.properties.get("lifecycle_state") or "active").casefold() == "active"


def _score(node: NodeSearchResult) -> float | None:
    value = node.properties.get("score")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _match_priority(match_kind: IdentityMatchKind) -> int:
    return {
        IdentityMatchKind.EXACT_NAME: 0,
        IdentityMatchKind.EXACT_ALIAS: 1,
        IdentityMatchKind.NAME_TOKEN: 2,
        IdentityMatchKind.FUZZY_HINT: 3,
    }[match_kind]


def _normalize(value: str) -> str:
    return normalize_text(value)


def _string_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list | tuple | set):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _unique_text(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _string_values(value):
            normalized = _normalize(item)
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(item)
    return result


def _guidance(status: IdentityLookupStatus) -> str:
    return {
        IdentityLookupStatus.NO_CANDIDATES: (
            "No deterministic existing identity candidate was found."
        ),
        IdentityLookupStatus.ONE_CANDIDATE: (
            "One deterministic existing identity candidate was found; review its supplied context."
        ),
        IdentityLookupStatus.MULTIPLE_CANDIDATES: (
            "Multiple deterministic candidates were found; do not assume they are the same person."
        ),
        IdentityLookupStatus.FUZZY_CANDIDATES_ONLY: (
            "Only fuzzy identity hints were found; they are not confirmed identity matches."
        ),
    }[status]
