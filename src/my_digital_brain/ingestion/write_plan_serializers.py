"""Candidate-to-write serializers used by the graph write-plan builder."""

from __future__ import annotations

from typing import Any

from my_digital_brain.graph.constants import NORMALIZED_NAME_LABELS
from my_digital_brain.graph.utils import normalize_text
from my_digital_brain.ingestion.contracts import (
    CandidateBase,
    CandidateClaim,
    CandidateEntity,
    CandidatePerception,
    CandidateProfileMemory,
    CandidateRelationship,
    CandidateRelationshipContext,
    GraphNodeWrite,
    GraphRelationshipWrite,
    MemoryLog,
    MemoryLogLink,
)
from my_digital_brain.ingestion.idempotency import deterministic_uuid, idempotency_key
from my_digital_brain.ingestion.write_plan_helpers import (
    _affective_properties,
    _base_properties,
    _base_relationship_properties,
    _drop_empty,
    _entity_allows_property,
    _entity_display_properties,
    _entity_typed_properties,
    _memory_log_extraction_run_ids,
    _memory_log_host_refs,
    _memory_log_involved_refs,
    _memory_log_relationship_context_refs,
    _memory_log_source_ids,
    _merge_listish_values,
    _primary_memory_log_host,
    _relationship_candidate_properties,
    _resolve_many,
    _resolve_ref_or_none,
    _source_ids,
    _temporal_properties,
)


class GraphWriteSerializersMixin:
    def _profile_memory_write(
        self,
        source_id: str,
        candidate: CandidateProfileMemory,
    ) -> GraphNodeWrite:
        key = idempotency_key(
            source_id,
            "profile_memory",
            candidate.local_ref,
            candidate.profile_key,
            candidate.value,
        )
        properties = _base_properties(source_id, candidate, key)
        properties.update(
            {
                "profile_key": candidate.profile_key,
                "category": candidate.category,
                "value": candidate.value,
                "stability": candidate.stability,
                "visibility": candidate.visibility,
                "description": candidate.description,
                "metadata": {
                    "original_user_words": candidate.original_user_words,
                    "assertion_mode": candidate.assertion_mode,
                    "reason": candidate.reason,
                    "requires_confirmation": candidate.requires_confirmation,
                    "owner_ref": "OWNER",
                },
            },
        )
        return GraphNodeWrite(
            local_ref=candidate.local_ref,
            label="ProfileMemory",
            properties=_drop_empty(properties),
            source_refs=_source_ids(candidate),
            evidence_refs=candidate.evidence_refs,
            idempotency_key=key,
        )

    def _entity_write(self, source_id: str, candidate: CandidateEntity) -> GraphNodeWrite:
        key = idempotency_key(source_id, "entity", candidate.local_ref, candidate.entity_type)
        properties = _base_properties(source_id, candidate, key)
        properties.update(_entity_display_properties(candidate))
        typed_properties, unsupported_properties = _entity_typed_properties(candidate)
        properties.update(typed_properties)
        if candidate.description:
            properties["description"] = candidate.description
        if candidate.aliases:
            if _entity_allows_property(candidate.entity_type, "aliases"):
                properties["aliases"] = candidate.aliases
            else:
                unsupported_properties["aliases"] = _merge_listish_values(
                    unsupported_properties.get("aliases"),
                    candidate.aliases,
                )
        if candidate.affective_fields:
            properties.update(_affective_properties(candidate.affective_fields))
        if candidate.entity_type in NORMALIZED_NAME_LABELS:
            name = properties.get("display_name") or properties.get("name")
            if isinstance(name, str) and name.strip():
                properties.setdefault("normalized_name", normalize_text(name))
        if unsupported_properties:
            properties["metadata"] = {
                **properties.get("metadata", {}),
                "unsupported_entity_properties": _drop_empty(unsupported_properties),
            }
        return GraphNodeWrite(
            local_ref=candidate.local_ref,
            label=candidate.entity_type,
            properties=properties,
            source_refs=_source_ids(candidate),
            evidence_refs=candidate.evidence_refs,
            idempotency_key=key,
        )

    def _claim_write(self, source_id: str, candidate: CandidateClaim) -> GraphNodeWrite:
        key = idempotency_key(source_id, "claim", candidate.local_ref, candidate.text)
        properties = _base_properties(source_id, candidate, key)
        properties.update(candidate.properties)
        properties.update({"text": candidate.text, "claim_type": candidate.claim_type})
        if candidate.valid_from:
            properties["valid_from"] = candidate.valid_from
        if candidate.valid_to:
            properties["valid_to"] = candidate.valid_to
        return GraphNodeWrite(
            local_ref=candidate.local_ref,
            label="Claim",
            properties=properties,
            source_refs=_source_ids(candidate),
            evidence_refs=candidate.evidence_refs,
            idempotency_key=key,
        )

    def _perception_write(self, source_id: str, candidate: CandidatePerception) -> GraphNodeWrite:
        key = idempotency_key(source_id, "perception", candidate.local_ref, candidate.target_ref)
        properties = _base_properties(source_id, candidate, key)
        properties.update(
            {
                "description": candidate.description,
                "perception_type": candidate.perception_type,
                "source_kind": candidate.source_kind,
                "emotional_summary": candidate.emotional_summary,
                "emotional_valence": candidate.emotional_valence,
                "emotional_intensity": candidate.emotional_intensity,
                "emotion_tags": candidate.emotion_tags,
                "original_user_words": candidate.original_user_words,
            },
        )
        properties.update(_temporal_properties(candidate.temporal_scope))
        return GraphNodeWrite(
            local_ref=candidate.local_ref,
            label="Perception",
            properties=_drop_empty(properties),
            source_refs=_source_ids(candidate),
            evidence_refs=candidate.evidence_refs,
            idempotency_key=key,
        )

    def _relationship_context_write(
        self,
        source_id: str,
        candidate: CandidateRelationshipContext,
    ) -> GraphNodeWrite:
        key = idempotency_key(
            source_id,
            "relationship_context",
            candidate.local_ref,
            candidate.from_ref,
            candidate.to_ref,
        )
        properties = _base_properties(source_id, candidate, key)
        properties.update(
            {
                "relationship_type": candidate.relationship_type,
                "relationship_kind": candidate.relationship_kind,
                "relationship_detail": candidate.relationship_detail,
                "status": candidate.status,
                "closeness": candidate.closeness,
                "description": candidate.description,
                "emotional_summary": candidate.emotional_summary,
                "emotional_valence": candidate.emotional_valence,
                "emotional_intensity": candidate.emotional_intensity,
                "emotion_tags": candidate.emotion_tags,
                "original_user_words": candidate.original_user_words,
            },
        )
        properties.update(_temporal_properties(candidate.temporal_scope))
        return GraphNodeWrite(
            local_ref=candidate.local_ref,
            label="RelationshipContext",
            properties=_drop_empty(properties),
            source_refs=_source_ids(candidate),
            evidence_refs=candidate.evidence_refs,
            idempotency_key=key,
        )

    def _memory_log_write(
        self,
        source_id: str,
        memory_log: MemoryLog,
        planned_ref_ids: dict[str, str],
    ) -> GraphNodeWrite:
        local_ref = memory_log.local_ref or memory_log.memory_log_id
        primary_host = memory_log.primary_host_target_id or _primary_memory_log_host(memory_log)
        key = idempotency_key(
            source_id,
            "memory_log",
            local_ref,
            memory_log.log_text,
            primary_host or "",
        )
        host_ids = _resolve_many(_memory_log_host_refs(memory_log), planned_ref_ids)
        involved_ids = _resolve_many(_memory_log_involved_refs(memory_log), planned_ref_ids)
        relationship_context_ids = _resolve_many(
            _memory_log_relationship_context_refs(memory_log),
            planned_ref_ids,
        )
        primary_host_id = _resolve_ref_or_none(primary_host, planned_ref_ids)
        properties: dict[str, Any] = {
            "id": deterministic_uuid(key),
            "description": memory_log.log_text,
            "log_text": memory_log.log_text,
            "log_kind": memory_log.log_kind,
            "source_kind": memory_log.source_kind,
            "importance": memory_log.importance,
            "happened_at": memory_log.happened_at,
            "primary_host_target_id": primary_host_id,
            "primary_host_target_label": memory_log.primary_host_target_label,
            "host_target_ids": host_ids,
            "involved_target_ids": involved_ids,
            "relationship_context_target_ids": relationship_context_ids,
            "media_refs": list(memory_log.media_refs),
            "source_ids": _memory_log_source_ids(memory_log) or [source_id],
            "extraction_run_ids": _memory_log_extraction_run_ids(memory_log),
            "original_user_words": memory_log.original_user_words,
            "confidence": memory_log.confidence,
            "lifecycle_state": memory_log.lifecycle_state,
            "metadata": {
                **memory_log.metadata,
                "memory_log_id": memory_log.memory_log_id,
                "candidate_local_ref": memory_log.local_ref,
                "idempotency_key": key,
            },
        }
        properties.update(_temporal_properties(memory_log.temporal_scope))
        return GraphNodeWrite(
            local_ref=local_ref,
            label="MemoryLog",
            properties=_drop_empty(properties),
            source_refs=_memory_log_source_ids(memory_log),
            evidence_refs=memory_log.evidence_refs,
            idempotency_key=key,
        )

    def _memory_log_relationship_write(
        self,
        *,
        source_id: str,
        memory_log: MemoryLog,
        link: MemoryLogLink,
        index: int,
    ) -> GraphRelationshipWrite:
        local_ref = memory_log.local_ref or memory_log.memory_log_id
        key = idempotency_key(
            source_id,
            "memory_log_relationship",
            local_ref,
            link.relationship_type,
            link.target_id,
            str(index),
        )
        properties = {
            "id": deterministic_uuid(key),
            "role": link.role,
            "primary": link.primary,
            "source_ids": _memory_log_source_ids(memory_log) or [source_id],
            "extraction_run_ids": _memory_log_extraction_run_ids(memory_log),
            "confidence": memory_log.confidence,
            "metadata": {
                "memory_log_local_ref": memory_log.local_ref,
                "memory_log_id": memory_log.memory_log_id,
                "target_label": link.target_label,
                "idempotency_key": key,
            },
        }
        if link.relationship_type == "HAS_MEMORY_LOG":
            from_ref = link.target_id
            to_ref = local_ref
        else:
            from_ref = local_ref
            to_ref = link.target_id
        return GraphRelationshipWrite(
            local_ref=f"{local_ref}_{link.relationship_type}_{index + 1:03d}",
            relationship_type=link.relationship_type,
            from_ref=from_ref,
            to_ref=to_ref,
            properties=_drop_empty(properties),
            source_refs=_memory_log_source_ids(memory_log),
            evidence_refs=memory_log.evidence_refs,
            idempotency_key=key,
        )

    def _candidate_relationship_write(
        self,
        source_id: str,
        candidate: CandidateRelationship,
    ) -> GraphRelationshipWrite:
        return self._relationship_write(
            source_id=source_id,
            local_ref=candidate.local_ref,
            relationship_type=candidate.relationship_type,
            from_ref=candidate.from_ref,
            to_ref=candidate.to_ref,
            candidate=candidate,
        )

    def _relationship_write(
        self,
        *,
        source_id: str,
        local_ref: str,
        relationship_type: str,
        from_ref: str,
        to_ref: str,
        candidate: CandidateBase,
    ) -> GraphRelationshipWrite:
        key = idempotency_key(source_id, "relationship", local_ref, relationship_type)
        properties = _base_relationship_properties(source_id, candidate, key)
        if isinstance(candidate, CandidateRelationship):
            candidate_properties = _relationship_candidate_properties(candidate)
            candidate_metadata = candidate_properties.pop("metadata", {})
            properties.update(candidate_properties)
            if candidate_metadata:
                properties["metadata"] = {
                    **properties.get("metadata", {}),
                    **candidate_metadata,
                }
        return GraphRelationshipWrite(
            local_ref=local_ref,
            relationship_type=relationship_type,
            from_ref=from_ref,
            to_ref=to_ref,
            properties=_drop_empty(properties),
            source_refs=_source_ids(candidate),
            evidence_refs=candidate.evidence_refs,
            idempotency_key=key,
        )

