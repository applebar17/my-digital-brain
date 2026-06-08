from __future__ import annotations

from dataclasses import dataclass

from my_digital_brain.ingestion.contracts import (
    CandidateEntity,
    GraphContextPack,
    ResolvedEntityMap,
    ResolvedEntityMapEntry,
    ResolvedEntityStatus,
)
from my_digital_brain.ingestion.ontology import LLMEntityType


@dataclass(slots=True)
class DeterministicResolvedEntityMapBuilder:
    """Conservative v1 entity resolution for the refined ingestion path."""

    def resolve(
        self,
        candidates: list[CandidateEntity],
        graph_context_pack: GraphContextPack,
    ) -> ResolvedEntityMap:
        index = _GraphContextEntityIndex.from_pack(graph_context_pack)
        seen_local_refs: set[str] = set()
        entries: list[ResolvedEntityMapEntry] = []
        for candidate in candidates:
            notes: list[str] = []
            if candidate.local_ref in seen_local_refs:
                entries.append(
                    _entry(
                        candidate,
                        status=ResolvedEntityStatus.REJECTED,
                        duplicate_notes=["Duplicate local_ref in entity candidate batch."],
                        resolution_reason="Local refs must be unique before relationship planning.",
                    ),
                )
                continue
            seen_local_refs.add(candidate.local_ref)
            if str(candidate.entity_type) not in {item.value for item in LLMEntityType}:
                entries.append(
                    _entry(
                        candidate,
                        status=ResolvedEntityStatus.REJECTED,
                        ambiguity_notes=[f"Unsupported entity type: {candidate.entity_type}"],
                        resolution_reason="Entity type is not allowed for LLM-created nodes.",
                    ),
                )
                continue
            match_ref = index.match_ref_for(candidate)
            if match_ref is not None:
                notes.append(f"Exact display name or alias matched existing ref {match_ref}.")
                entries.append(
                    _entry(
                        candidate,
                        status=ResolvedEntityStatus.MATCHED_EXISTING,
                        graph_alias=match_ref,
                        duplicate_notes=notes,
                        resolution_reason="Deterministic exact graph-context match.",
                    ),
                )
                continue
            entries.append(
                _entry(
                    candidate,
                    status=ResolvedEntityStatus.STAGED_CREATE,
                    resolution_reason="No exact deterministic graph-context match.",
                ),
            )
        return ResolvedEntityMap(entries=entries)


class _GraphContextEntityIndex:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    @classmethod
    def from_pack(cls, pack: GraphContextPack) -> "_GraphContextEntityIndex":
        values: dict[str, str] = {}
        for entity in pack.entities:
            _add(values, entity.display_label, entity.ref)
            for alias in entity.aliases:
                _add(values, alias, entity.ref)
        for alias in pack.known_aliases:
            if alias.target_ref:
                _add(values, alias.alias, alias.target_ref)
            if alias.label and alias.target_ref:
                _add(values, alias.label, alias.target_ref)
        for hint in pack.duplicate_hints:
            if len(hint.possible_match_refs) == 1:
                _add(values, hint.candidate_text, hint.possible_match_refs[0])
        return cls(values)

    def match_ref_for(self, candidate: CandidateEntity) -> str | None:
        for value in _candidate_match_values(candidate):
            match = self.values.get(_normalize(value))
            if match is not None:
                return match
        return None


def _entry(
    candidate: CandidateEntity,
    *,
    status: ResolvedEntityStatus,
    graph_alias: str | None = None,
    duplicate_notes: list[str] | None = None,
    ambiguity_notes: list[str] | None = None,
    resolution_reason: str | None = None,
) -> ResolvedEntityMapEntry:
    return ResolvedEntityMapEntry(
        local_ref=candidate.local_ref,
        status=status,
        display_label=candidate.display_name or candidate.description,
        entity_type=str(candidate.entity_type),
        graph_alias=graph_alias,
        duplicate_notes=duplicate_notes or [],
        ambiguity_notes=ambiguity_notes or [],
        resolution_reason=resolution_reason,
    )


def _candidate_match_values(candidate: CandidateEntity) -> list[str]:
    return [
        value
        for value in [
            candidate.display_name,
            candidate.description,
            *candidate.aliases,
        ]
        if isinstance(value, str) and value.strip()
    ]


def _add(values: dict[str, str], key: str | None, ref: str) -> None:
    normalized = _normalize(key)
    if normalized:
        values.setdefault(normalized, ref)


def _normalize(value: str | None) -> str:
    return " ".join(str(value or "").strip().casefold().split())
