"""Shared serialization helpers for backend graph write planning."""

from __future__ import annotations

from typing import Any

from my_digital_brain.graph.constants import AFFECTIVE_FIELD_NAMES
from my_digital_brain.graph.models import node_model_for_label
from my_digital_brain.ingestion.contracts import (
    AffectiveFields,
    CandidateBase,
    CandidateEntity,
    CandidateRelationship,
    MemoryLog,
    MemoryLogLink,
    TemporalScope,
)
from my_digital_brain.ingestion.idempotency import deterministic_uuid
def _memory_log_links(memory_log: MemoryLog) -> list[MemoryLogLink]:
    links: list[MemoryLogLink] = []
    seen: set[tuple[str, str, str | None, bool]] = set()
    primary_host = memory_log.primary_host_target_id or _primary_memory_log_host(memory_log)

    def add(link: MemoryLogLink) -> None:
        key = (link.relationship_type, link.target_id, link.role, link.primary)
        if key not in seen:
            links.append(link)
            seen.add(key)

    for link in memory_log.links:
        if (
            link.relationship_type == "HAS_MEMORY_LOG"
            and primary_host
            and link.target_id == primary_host
            and not link.primary
        ):
            link = link.model_copy(update={"primary": True})
        add(link)

    explicit_host_targets = {
        link.target_id for link in links if link.relationship_type == "HAS_MEMORY_LOG"
    }
    for target_id in memory_log.host_target_ids:
        if target_id in explicit_host_targets:
            continue
        add(
            MemoryLogLink(
                target_id=target_id,
                relationship_type="HAS_MEMORY_LOG",
                primary=target_id == primary_host,
            )
        )
    if (
        memory_log.primary_host_target_id
        and memory_log.primary_host_target_id not in explicit_host_targets
        and memory_log.primary_host_target_id not in memory_log.host_target_ids
    ):
        add(
            MemoryLogLink(
                target_id=memory_log.primary_host_target_id,
                target_label=memory_log.primary_host_target_label,
                relationship_type="HAS_MEMORY_LOG",
                primary=True,
            )
        )

    explicit_involved_targets = {
        link.target_id for link in links if link.relationship_type == "INVOLVES"
    }
    for target_id in memory_log.involved_target_ids:
        if target_id not in explicit_involved_targets:
            add(MemoryLogLink(target_id=target_id, relationship_type="INVOLVES"))

    return links


def _memory_log_host_refs(memory_log: MemoryLog) -> list[str]:
    refs = list(memory_log.host_target_ids)
    refs.extend(
        link.target_id
        for link in memory_log.links
        if link.relationship_type == "HAS_MEMORY_LOG"
    )
    if memory_log.primary_host_target_id:
        refs.append(memory_log.primary_host_target_id)
    return _unique(refs)


def _memory_log_involved_refs(memory_log: MemoryLog) -> list[str]:
    refs = list(memory_log.involved_target_ids)
    refs.extend(
        link.target_id for link in memory_log.links if link.relationship_type == "INVOLVES"
    )
    return _unique(refs)


def _memory_log_relationship_context_refs(memory_log: MemoryLog) -> list[str]:
    return _unique(
        link.target_id
        for link in memory_log.links
        if link.relationship_type == "UPDATES_RELATIONSHIP"
    )


def _primary_memory_log_host(memory_log: MemoryLog) -> str | None:
    for link in memory_log.links:
        if link.relationship_type == "HAS_MEMORY_LOG" and link.primary:
            return link.target_id
    if len(memory_log.host_target_ids) == 1:
        return memory_log.host_target_ids[0]
    return None


def _resolve_many(refs: list[str], planned_ref_ids: dict[str, str]) -> list[str]:
    return _unique(_resolve_ref_or_none(ref, planned_ref_ids) for ref in refs)


def _resolve_ref_or_none(ref: str | None, planned_ref_ids: dict[str, str]) -> str | None:
    if not ref:
        return None
    return planned_ref_ids.get(ref, ref)


def _memory_log_source_ids(memory_log: MemoryLog) -> list[str]:
    source_ids = list(memory_log.source_refs)
    source_ids.extend(evidence.source_id for evidence in memory_log.evidence_refs)
    return _unique(source_ids)


def _memory_log_extraction_run_ids(memory_log: MemoryLog) -> list[str]:
    refs = list(memory_log.extraction_run_ids)
    refs.extend(
        evidence.extraction_run_id
        for evidence in memory_log.evidence_refs
        if evidence.extraction_run_id
    )
    return _unique(refs)


def _base_properties(source_id: str, candidate: CandidateBase, key: str) -> dict[str, Any]:
    return {
        "id": deterministic_uuid(key),
        "source_ids": _source_ids(candidate) or [source_id],
        "extraction_run_ids": _extraction_run_ids(candidate),
        "metadata": {
            "candidate_local_ref": candidate.local_ref,
            "candidate_metadata": candidate.metadata,
            "idempotency_key": key,
        },
    }


def _base_relationship_properties(
    source_id: str,
    candidate: CandidateBase,
    key: str,
) -> dict[str, Any]:
    return {
        "id": deterministic_uuid(key),
        "source_ids": _source_ids(candidate) or [source_id],
        "extraction_run_ids": _extraction_run_ids(candidate),
        "metadata": {
            "candidate_local_ref": candidate.local_ref,
            "candidate_metadata": candidate.metadata,
            "idempotency_key": key,
        },
    }


def _entity_display_properties(candidate: CandidateEntity) -> dict[str, Any]:
    display_name = candidate.display_name
    if not display_name:
        return {}
    if candidate.entity_type == "Person":
        return {"display_name": display_name}
    if candidate.entity_type == "Event":
        return {"title": display_name}
    return {"name": display_name}


def _entity_typed_properties(candidate: CandidateEntity) -> tuple[dict[str, Any], dict[str, Any]]:
    allowed_fields = set(node_model_for_label(candidate.entity_type).model_fields)
    properties: dict[str, Any] = {}
    unsupported_properties: dict[str, Any] = {}
    for key, value in candidate.typed_properties.items():
        target = (
            properties
            if key in allowed_fields and key not in _ENTITY_PROTECTED_FIELDS
            else unsupported_properties
        )
        target[key] = value
    return properties, unsupported_properties


def _entity_allows_property(label: str, property_name: str) -> bool:
    return property_name in node_model_for_label(label).model_fields


def _relationship_candidate_properties(candidate: CandidateRelationship) -> dict[str, Any]:
    properties = dict(candidate.properties)
    if candidate.relationship_kind:
        properties["relationship_kind"] = candidate.relationship_kind
    if candidate.relationship_detail:
        properties["relationship_detail"] = candidate.relationship_detail
    metadata = dict(properties.pop("metadata", {}))
    for key, value in list(properties.items()):
        if key not in _RELATIONSHIP_PROPERTY_FIELDS:
            metadata[key] = properties.pop(key)
    if candidate.affective_fields:
        properties.update(_affective_properties(candidate.affective_fields))
    properties.update(_temporal_properties(candidate.temporal_scope))
    if metadata:
        existing = properties.get("metadata")
        properties["metadata"] = {**(existing or {}), **metadata}
    return properties


def _affective_properties(affective: AffectiveFields) -> dict[str, Any]:
    return {
        key: value
        for key, value in affective.model_dump(mode="python", exclude_none=True).items()
        if key in AFFECTIVE_FIELD_NAMES or key == "description"
    }


def _temporal_properties(scope: TemporalScope | None) -> dict[str, Any]:
    if scope is None:
        return {}
    return scope.model_dump(mode="python", exclude_none=True)


def _source_ids(candidate: CandidateBase) -> list[str]:
    source_ids = list(candidate.source_refs)
    source_ids.extend(evidence.source_id for evidence in candidate.evidence_refs)
    return _unique(source_ids)


def _extraction_run_ids(candidate: CandidateBase) -> list[str]:
    return _unique(
        evidence.extraction_run_id
        for evidence in candidate.evidence_refs
        if evidence.extraction_run_id
    )


def _unique(values) -> list[str]:
    unique_values: list[str] = []
    for value in values:
        if value and value not in unique_values:
            unique_values.append(value)
    return unique_values


def _merge_listish_values(current: Any, next_value: Any) -> Any:
    current_values = _listish_values(current)
    next_values = _listish_values(next_value)
    if current_values or next_values:
        return _unique([*current_values, *next_values])
    return next_value


def _listish_values(value: Any) -> list[Any]:
    if value in (None, "", []):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _drop_empty(properties: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in properties.items() if value not in (None, "", [])}


_ENTITY_PROTECTED_FIELDS = {
    "id",
    "created_at",
    "updated_at",
    "source_ids",
    "extraction_run_ids",
    "metadata",
}

_RELATIONSHIP_PROPERTY_FIELDS = {
    "id",
    "description",
    "relationship_kind",
    "relationship_detail",
    "valid_from",
    "valid_to",
    "resolved_start",
    "resolved_end",
    "time_precision",
    "time_basis",
    "timezone",
    "original_time_text",
    "emotional_summary",
    "emotional_valence",
    "emotional_intensity",
    "emotion_tags",
    "original_user_words",
    "role",
    "primary",
    "confidence",
    "trust_level",
    "privacy_level",
    "lifecycle_state",
    "source_ids",
    "extraction_run_ids",
    "metadata",
}
