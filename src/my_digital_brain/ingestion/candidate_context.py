from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Iterable

from my_digital_brain.core.enums import PrivacyLevel
from my_digital_brain.graph.constants import OWNER_ALIAS
from my_digital_brain.graph.exceptions import GraphNotFoundError
from my_digital_brain.graph.models import NodeSearchResult, RelationshipResult
from my_digital_brain.ingestion.contracts import (
    EntityLookupCandidate,
    EntityLookupContextPacket,
    EntityLookupRelatedContext,
    IdentityLookupStatus,
    ReferenceObjectKind,
)
from my_digital_brain.ingestion.identity_lookup import IdentityLookupError
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry


class CandidateContextHydrationError(IdentityLookupError):
    """Raised when candidate context cannot be read safely."""


_MODEL_REF_RE = re.compile(
    r"\b(?:OWNER|(?:NODE|REL|MEMORY|CONTEXT|MEDIA|SOURCE|CLAIM)_\d{6})\b",
)
_TEMPORAL_FIELDS = (
    "happened_at",
    "resolved_start",
    "valid_from",
    "source_time",
    "observed_at",
)
_DISALLOWED_PRIVACY = {
    PrivacyLevel.HIDDEN.value,
    PrivacyLevel.LOCAL_ONLY.value,
}


@dataclass(slots=True)
class BoundedCandidateContextHydrator:
    """Hydrate bounded, graph-grounded evidence around lookup candidates."""

    graph_service: Any
    owner_graph_node_id: str | None = None
    max_relationships: int = 3
    max_memory_logs: int = 3
    max_summary_chars: int = 500
    max_total_chars: int = 6000

    def hydrate_packets(
        self,
        packets: Iterable[EntityLookupContextPacket],
        *,
        registry: RunReferenceRegistry,
    ) -> list[EntityLookupContextPacket]:
        hydrated = [
            self._hydrate_packet(packet, registry=registry)
            for packet in packets
        ]
        return self._limit_total(hydrated, registry=registry)

    def _hydrate_packet(
        self,
        packet: EntityLookupContextPacket,
        *,
        registry: RunReferenceRegistry,
    ) -> EntityLookupContextPacket:
        candidates = []
        for candidate in packet.lookup.candidates:
            hydrated = self._hydrate_candidate(candidate, registry=registry)
            if hydrated is not None:
                candidates.append(hydrated)
        status = packet.lookup.status
        if not candidates:
            status = IdentityLookupStatus.NO_CANDIDATES
        elif status != IdentityLookupStatus.FUZZY_CANDIDATES_ONLY:
            status = (
                IdentityLookupStatus.ONE_CANDIDATE
                if len(candidates) == 1
                else IdentityLookupStatus.MULTIPLE_CANDIDATES
            )
        lookup = packet.lookup.model_copy(update={"status": status, "candidates": candidates})
        return packet.model_copy(update={"lookup": lookup})

    def _hydrate_candidate(
        self,
        candidate: EntityLookupCandidate,
        *,
        registry: RunReferenceRegistry,
    ) -> EntityLookupCandidate | None:
        try:
            candidate_id = registry.resolve(
                candidate.ref,
                expected_kind=ReferenceObjectKind.NODE,
            )
            candidate_node = self._get_node(candidate_id)
            if (
                getattr(self.graph_service, "get_node", None) is not None
                and (candidate_node is None or not self._is_visible_node(candidate_node))
            ):
                return None
            relationships = self._relationships(candidate_id)
            related_summaries: list[str] = []
            place_hints: list[str] = []
            temporal_hints = self._temporal_hints(candidate_node or candidate)
            for relationship in relationships:
                context = self._relationship_context(
                    candidate,
                    candidate_id,
                    relationship,
                    registry,
                )
                if context is None:
                    continue
                summary, related_node = context
                related_summaries.append(summary)
                if related_node.label == "Place":
                    name = self._safe_node_title(related_node)
                    city = _first_text(related_node.properties, "city", "region", "country")
                    place_hints.append(f"{name} ({city})" if city else name)
                temporal_hints.extend(self._temporal_hints(related_node))

            memory_summaries = self._memory_summaries(candidate_id, registry)
            related_context = EntityLookupRelatedContext(
                relationship_summaries=_unique_limited(
                    related_summaries,
                    self.max_relationships,
                    self.max_summary_chars,
                ),
                relevant_memory_summaries=_unique_limited(
                    memory_summaries,
                    self.max_memory_logs,
                    self.max_summary_chars,
                ),
                place_hints=_unique_limited(
                    place_hints,
                    self.max_relationships,
                    self.max_summary_chars,
                ),
                temporal_hints=_unique_limited(
                    temporal_hints,
                    self.max_relationships,
                    self.max_summary_chars,
                ),
            )
            return candidate.model_copy(
                update={
                    "display_name": self._redact(candidate.display_name, registry),
                    "aliases": [
                        self._redact(alias, registry)
                        for alias in candidate.aliases
                        if alias.strip()
                    ],
                    "related_context": related_context,
                },
            )
        except GraphNotFoundError:
            return candidate.model_copy(
                update={"related_context": EntityLookupRelatedContext()},
            )
        except CandidateContextHydrationError:
            raise
        except Exception as exc:
            raise CandidateContextHydrationError(
                "Candidate context hydration failed.",
            ) from exc

    def _relationships(self, node_id: str) -> list[RelationshipResult]:
        if self.max_relationships <= 0:
            return []
        getter = getattr(self.graph_service, "get_node_relationships", None)
        if getter is None:
            return []
        relationships = [
            RelationshipResult.model_validate(item)
            for item in getter(
                node_id,
                direction="both",
                limit=max(self.max_relationships * 4, 12),
            )
            if self._is_visible_relationship(item)
        ]
        return sorted(
            relationships,
            key=lambda item: (
                item.type,
                str(item.properties.get("relationship_detail") or "").casefold(),
                str(item.properties.get("id") or ""),
            ),
        )[: self.max_relationships]

    def _relationship_context(
        self,
        candidate: EntityLookupCandidate,
        candidate_id: str,
        relationship: RelationshipResult,
        registry: RunReferenceRegistry,
    ) -> tuple[str, NodeSearchResult] | None:
        other_id = (
            relationship.to_id
            if str(relationship.from_id) == candidate_id
            else relationship.from_id
        )
        related_node = self._get_node(str(other_id))
        if related_node is None or not self._is_visible_node(related_node):
            return None
        related_ref = self._register_node(related_node, registry)
        if related_ref is None:
            return None
        relationship_ref = registry.register_existing(
            str(
                relationship.properties.get("id")
                or f"{relationship.from_id}:{relationship.type}:{relationship.to_id}"
            ),
            object_kind=ReferenceObjectKind.EDGE,
            label=relationship.type,
            display_label=relationship.type,
        )
        detail = _first_text(
            relationship.properties,
            "relationship_detail",
            "description",
            "relationship_kind",
            "role",
        )
        related_title = self._safe_node_title(related_node)
        relation_text = f"{candidate.ref} -> {related_ref} [{relationship.type}]"
        if related_title:
            relation_text += f" ({related_title})"
        if detail:
            relation_text += f": {detail}"
        original_words = relationship.properties.get("original_user_words")
        if original_words:
            relation_text += f" {_user_evidence(self._redact(str(original_words), registry))}"
        relation_text = f"{relationship_ref}: {relation_text}"
        return self._redact(relation_text, registry), related_node

    def _memory_summaries(
        self,
        node_id: str,
        registry: RunReferenceRegistry,
    ) -> list[str]:
        if self.max_memory_logs <= 0:
            return []
        getter = getattr(self.graph_service, "get_memory_logs_for_target", None)
        if getter is None:
            return []
        logs = getter(
            node_id,
            include_archived=False,
            limit=max(self.max_memory_logs * 4, 12),
        )
        summaries: list[str] = []
        visible_logs = [
            NodeSearchResult.model_validate(raw_log)
            for raw_log in logs or []
        ]
        visible_logs = [log for log in visible_logs if self._is_visible_node(log)]
        visible_logs.sort(
            key=lambda log: (
                _first_text(log.properties, *_TEMPORAL_FIELDS) or "",
                str(log.properties.get("id") or ""),
            ),
            reverse=True,
        )
        for log in visible_logs[: self.max_memory_logs]:
            log_id = log.properties.get("id")
            if not log_id:
                continue
            memory_ref = registry.register_existing(
                str(log_id),
                object_kind=ReferenceObjectKind.MEMORY,
                label=log.label,
                display_label="Memory log",
            )
            text = _first_text(log.properties, "log_text", "description")
            if not text:
                continue
            summary = f"{memory_ref}: {text}"
            original_words = log.properties.get("original_user_words")
            if original_words and str(original_words).strip() != text.strip():
                summary += f" {_user_evidence(str(original_words))}"
            happened_at = _first_text(log.properties, *_TEMPORAL_FIELDS)
            if happened_at:
                summary += f" ({happened_at})"
            summaries.append(self._redact(summary, registry))
        return summaries

    def _get_node(self, node_id: str) -> NodeSearchResult | None:
        getter = getattr(self.graph_service, "get_node", None)
        if getter is None:
            return None
        try:
            raw_node = getter(node_id)
        except GraphNotFoundError:
            return None
        if raw_node is None:
            return None
        return NodeSearchResult.model_validate(raw_node)

    def _register_node(
        self,
        node: NodeSearchResult,
        registry: RunReferenceRegistry,
    ) -> str | None:
        node_id = str(node.properties.get("id") or "")
        if not node_id:
            return None
        if self.owner_graph_node_id and node_id == self.owner_graph_node_id:
            try:
                entry = registry.entry_for(OWNER_ALIAS)
            except ValueError:
                return None
            return entry.ref
        return registry.register_existing(
            node_id,
            object_kind=ReferenceObjectKind.NODE,
            label=node.label,
            display_label=self._safe_node_title(node),
            aliases=[
                value
                for value in _string_values(node.properties.get("aliases"))
                if value != node_id and not _MODEL_REF_RE.fullmatch(value)
            ],
        )

    def _safe_node_title(self, node: NodeSearchResult) -> str:
        return _first_text(
            node.properties,
            "display_name",
            "name",
            "title",
            "profile_key",
            "value",
        ) or node.label

    def _temporal_hints(self, node_or_candidate: Any) -> list[str]:
        properties = getattr(node_or_candidate, "properties", None)
        if properties is None:
            properties = {
                "known_since": getattr(node_or_candidate, "known_since", None),
            }
        return [
            str(properties[field])
            for field in (*_TEMPORAL_FIELDS, "known_since")
            if properties.get(field) not in (None, "", [])
        ]

    def _is_visible_node(self, node: NodeSearchResult) -> bool:
        properties = node.properties
        lifecycle = str(properties.get("lifecycle_state") or "active").casefold()
        return (
            lifecycle == "active"
            and not properties.get("merged_into_id")
            and not _privacy_disallowed(properties)
        )

    def _is_visible_relationship(self, relationship: Any) -> bool:
        properties = getattr(relationship, "properties", None)
        if properties is None and isinstance(relationship, dict):
            properties = relationship.get("properties", {})
        properties = properties or {}
        lifecycle = str(properties.get("lifecycle_state") or "active").casefold()
        return lifecycle == "active" and not _privacy_disallowed(properties)

    def _redact(self, value: str | None, registry: RunReferenceRegistry) -> str | None:
        if value is None:
            return None
        redacted = str(value)
        mappings = sorted(registry.backend_alias_map().items(), key=lambda item: -len(str(item[1])))
        for ref, backend_id in mappings:
            if backend_id:
                redacted = redacted.replace(str(backend_id), ref)
        return redacted

    def _limit_total(
        self,
        packets: list[EntityLookupContextPacket],
        *,
        registry: RunReferenceRegistry,
    ) -> list[EntityLookupContextPacket]:
        while len(_serialized_packets(packets)) > self.max_total_chars:
            location = _longest_context_item(packets)
            if location is None:
                break
            packet_index, candidate_index, field, item_index, value = location
            shortened = _shorten(value)
            packet = packets[packet_index]
            candidates = list(packet.lookup.candidates)
            candidate = candidates[candidate_index]
            related = candidate.related_context.model_copy()
            values = list(getattr(related, field))
            if shortened:
                values[item_index] = self._redact(shortened, registry) or ""
            else:
                values.pop(item_index)
            setattr(related, field, values)
            candidates[candidate_index] = candidate.model_copy(update={"related_context": related})
            packets[packet_index] = packet.model_copy(
                update={"lookup": packet.lookup.model_copy(update={"candidates": candidates})},
            )
        return packets

def packets_for_references(
    packets: Iterable[EntityLookupContextPacket],
    references: Iterable[str],
) -> list[EntityLookupContextPacket]:
    """Select packets relevant to one focused extraction task or batch."""

    required = {str(ref) for ref in references if ref}
    if not required:
        return []
    selected: list[EntityLookupContextPacket] = []
    for packet in packets:
        packet_refs = {packet.candidate_ref}
        packet_refs.update(candidate.ref for candidate in packet.lookup.candidates)
        if packet_refs & required:
            selected.append(packet)
    return selected


def _privacy_disallowed(properties: dict[str, Any]) -> bool:
    return str(properties.get("privacy_level") or PrivacyLevel.NORMAL.value) in _DISALLOWED_PRIVACY


def _first_text(properties: dict[str, Any], *fields: str) -> str | None:
    for field in fields:
        value = properties.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _string_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _user_evidence(value: str) -> str:
    safe = value.replace("[USER_EVIDENCE]", "[USER_DATA]").replace(
        "[/USER_EVIDENCE]", "[/USER_DATA]"
    )
    return f"[USER_EVIDENCE] {safe} [/USER_EVIDENCE]"


def _unique_limited(values: list[str], limit: int, max_chars: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(value[:max_chars])
        if len(result) >= limit:
            break
    return result


def _serialized_packets(packets: list[EntityLookupContextPacket]) -> str:
    return json.dumps(
        [packet.model_dump(mode="json", exclude_none=True) for packet in packets],
        ensure_ascii=False,
        sort_keys=True,
    )


def _longest_context_item(
    packets: list[EntityLookupContextPacket],
) -> tuple[int, int, str, int, str] | None:
    longest: tuple[int, int, str, int, str] | None = None
    for packet_index, packet in enumerate(packets):
        for candidate_index, candidate in enumerate(packet.lookup.candidates):
            context = candidate.related_context
            for field in (
                "relationship_summaries",
                "relevant_memory_summaries",
                "place_hints",
                "temporal_hints",
            ):
                for item_index, value in enumerate(getattr(context, field)):
                    if longest is None or len(value) > len(longest[-1]):
                        longest = (packet_index, candidate_index, field, item_index, value)
    return longest


def _shorten(value: str) -> str:
    if len(value) <= 45:
        return ""
    return value[: max(20, len(value) // 2)].rstrip() + "..."
