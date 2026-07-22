"""Compact model-facing context for batched resolution sessions."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from my_digital_brain.ingestion.contracts import CandidateMemoryGraph

_MAX_ITEMS = 32
_MAX_ITEM_CHARS = 220
_MAX_PACKET_CHARS = 4000


def build_other_planned_context_packet(
    candidate_graph: CandidateMemoryGraph,
    *,
    excluded_refs: Iterable[str],
) -> str:
    """Render references outside the active batch without exposing backend IDs."""

    excluded = set(excluded_refs)
    lines: list[str] = []
    for candidate in _planned_items(candidate_graph):
        local_ref = getattr(candidate, "local_ref", None)
        if not local_ref or local_ref in excluded:
            continue
        lines.append(f"- {local_ref}: {_summary(candidate)}")
        if len(lines) >= _MAX_ITEMS:
            break
    if not lines:
        return ""
    packet = (
        "Other relevant planned ingestions (reference-only):\n"
        + "\n".join(lines)
        + "\nThese references are valid for evidence and relationship endpoints "
        "within this resolution session. Do not submit a terminal action for them "
        "unless they are included in the current candidate batch."
    )
    return packet[:_MAX_PACKET_CHARS]


def _planned_items(candidate_graph: CandidateMemoryGraph) -> list[Any]:
    return [
        *candidate_graph.candidate_entities,
        *candidate_graph.memory_logs,
        *candidate_graph.candidate_profile_memories,
        *candidate_graph.candidate_relationships,
        *candidate_graph.candidate_relationship_contexts,
        *candidate_graph.candidate_claims,
        *candidate_graph.candidate_perceptions,
        *candidate_graph.candidate_metadata_patches,
    ]


def _summary(candidate: Any) -> str:
    if hasattr(candidate, "entity_type"):
        parts = [
            str(getattr(candidate, "entity_type", "entity")),
            str(getattr(candidate, "display_name", None) or "unnamed"),
        ]
        aliases = getattr(candidate, "aliases", None) or []
        if aliases:
            parts.append(f"aliases: {', '.join(str(alias) for alias in aliases[:4])}")
        description = getattr(candidate, "description", None)
        if description:
            parts.append(str(description))
        return _compact("; ".join(parts))
    if hasattr(candidate, "log_text"):
        return _compact(f"memory log; {getattr(candidate, 'log_text', '')}")
    if hasattr(candidate, "relationship_type"):
        return _compact(
            f"relationship {getattr(candidate, 'relationship_type', 'unknown')}; "
            f"{getattr(candidate, 'from_ref', '?')} -> {getattr(candidate, 'to_ref', '?')}"
        )
    if hasattr(candidate, "profile_key"):
        return _compact(
            f"profile {getattr(candidate, 'profile_key', 'unknown')}: "
            f"{getattr(candidate, 'value', '')}"
        )
    if hasattr(candidate, "path"):
        return _compact(
            f"metadata patch {getattr(candidate, 'target_ref', '?')}."
            f"{getattr(candidate, 'path', '')}"
        )
    if hasattr(candidate, "text"):
        return _compact(f"claim; {getattr(candidate, 'text', '')}")
    if hasattr(candidate, "target_ref") and hasattr(candidate, "description"):
        return _compact(
            f"perception of {getattr(candidate, 'target_ref', '?')}; "
            f"{getattr(candidate, 'description', '')}"
        )
    return _compact(str(candidate))


def _compact(value: str) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= _MAX_ITEM_CHARS:
        return normalized
    return normalized[: _MAX_ITEM_CHARS - 3].rstrip() + "..."
