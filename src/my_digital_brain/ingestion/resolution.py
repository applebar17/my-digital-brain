from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from my_digital_brain.graph.models import NodeSearchResult
from my_digital_brain.graph.utils import normalize_text
from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    CandidateMemoryGraph,
    ClarificationRequest,
    IngestionContextPackage,
    ResolutionDecision,
    ResolutionResult,
)
from my_digital_brain.ingestion.enums import ResolutionDecisionType


class ConservativeResolutionService:
    """Resolve only exact, unambiguous matches and defer risky cases."""

    def __init__(self, graph_service: Any, *, search_limit: int = 5) -> None:
        self.graph_service = graph_service
        self.search_limit = search_limit

    def resolve(
        self,
        candidate_graph: CandidateMemoryGraph,
        context: IngestionContextPackage | None = None,
    ) -> ResolutionResult:
        decisions: list[ResolutionDecision] = []
        clarification_targets: list[str] = []
        clarification_options: list[str] = []
        reasons: list[str] = []

        for candidate in candidate_graph.candidate_entities:
            decision, options, reason = self._resolve_entity(candidate)
            decisions.append(decision)
            if decision.decision_type == ResolutionDecisionType.ASK_CLARIFICATION:
                clarification_targets.append(candidate.local_ref)
                clarification_options.extend(options)
                reasons.append(reason or f"Ambiguous candidate {candidate.local_ref}.")

        clarification = None
        if clarification_targets:
            clarification = ClarificationRequest(
                question="Which existing memory should this refer to?",
                reason="; ".join(reasons),
                target_refs=clarification_targets,
                options=sorted(set(clarification_options)),
                blocking=True,
            )

        return ResolutionResult(
            decisions=decisions,
            clarification=clarification,
            metadata={"policy": "exact_match_only"},
        )

    def _resolve_entity(
        self,
        candidate: CandidateEntity,
    ) -> tuple[ResolutionDecision, list[str], str | None]:
        search_text = _candidate_search_text(candidate)
        if not search_text:
            return self._decision(
                candidate,
                ResolutionDecisionType.CREATE,
                reasons=["No searchable name was extracted."],
            ), [], None

        matches = self.graph_service.search_nodes(
            label=candidate.entity_type,
            query=search_text,
            limit=self.search_limit,
        )
        exact_matches = [
            node for node in matches if _node_matches_candidate(node, candidate, search_text)
        ]
        if len(exact_matches) == 1:
            node = exact_matches[0]
            return self._decision(
                candidate,
                ResolutionDecisionType.MATCH_EXISTING,
                target_entity_id=node.properties["id"],
                scores={"exact_name": 1.0},
                reasons=[f"Exactly matched existing {candidate.entity_type}: {search_text}."],
            ), [], None

        if len(exact_matches) > 1 or len(matches) > 1:
            options = [_node_option(node) for node in exact_matches or matches]
            reason = (
                f"Candidate '{search_text}' matched multiple existing "
                f"{candidate.entity_type} nodes."
            )
            return self._decision(
                candidate,
                ResolutionDecisionType.ASK_CLARIFICATION,
                reasons=[reason],
                requires_confirmation=True,
            ), options, reason

        return self._decision(
            candidate,
            ResolutionDecisionType.CREATE,
            reasons=[f"No exact existing {candidate.entity_type} match found."],
        ), [], None

    def _decision(
        self,
        candidate: CandidateEntity,
        decision_type: ResolutionDecisionType,
        *,
        target_entity_id: str | None = None,
        scores: dict[str, float] | None = None,
        reasons: list[str] | None = None,
        requires_confirmation: bool = False,
    ) -> ResolutionDecision:
        return ResolutionDecision(
            candidate_ref=candidate.local_ref,
            decision_type=decision_type,
            target_entity_id=target_entity_id,
            scores=scores or {},
            reasons=reasons or [],
            requires_confirmation=requires_confirmation,
            decided_at=datetime.now(UTC),
        )


def _candidate_search_text(candidate: CandidateEntity) -> str | None:
    for value in (
        candidate.display_name,
        candidate.typed_properties.get("name"),
        candidate.typed_properties.get("title"),
        candidate.typed_properties.get("normalized_name"),
        *candidate.aliases,
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _node_matches_candidate(
    node: NodeSearchResult,
    candidate: CandidateEntity,
    search_text: str,
) -> bool:
    normalized_targets = {normalize_text(search_text)}
    normalized_targets.update(normalize_text(alias) for alias in candidate.aliases)
    node_values = [
        node.properties.get("display_name"),
        node.properties.get("name"),
        node.properties.get("title"),
        node.properties.get("normalized_name"),
        *node.properties.get("aliases", []),
    ]
    return any(
        isinstance(value, str) and normalize_text(value) in normalized_targets
        for value in node_values
    )


def _node_option(node: NodeSearchResult) -> str:
    for field in ("display_name", "name", "title", "description"):
        value = node.properties.get(field)
        if isinstance(value, str) and value.strip():
            return f"{value} ({node.label}, {node.properties['id']})"
    return f"{node.label} {node.properties['id']}"
