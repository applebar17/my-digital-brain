from __future__ import annotations

from typing import Any

from my_digital_brain.graph.constants import AFFECTIVE_FIELD_NAMES, NORMALIZED_NAME_LABELS
from my_digital_brain.graph.utils import normalize_text
from my_digital_brain.ingestion.contracts import (
    AffectiveFields,
    CandidateBase,
    CandidateClaim,
    CandidateEntity,
    CandidateMemoryGraph,
    CandidatePerception,
    CandidateRelationship,
    CandidateRelationshipContext,
    EvidenceRef,
    GraphNodeWrite,
    GraphRelationshipWrite,
    GraphWritePlan,
    IngestionContextPackage,
    ResolutionDecision,
    ResolutionResult,
    TemporalScope,
)
from my_digital_brain.ingestion.enums import GraphWritePlanStatus, ResolutionDecisionType
from my_digital_brain.ingestion.exceptions import IngestionValidationError
from my_digital_brain.ingestion.idempotency import deterministic_uuid, idempotency_key


class GraphWritePlanBuilder:
    """Build deterministic, backend-owned graph write commands."""

    def build(
        self,
        candidate_graph: CandidateMemoryGraph,
        resolution: ResolutionResult,
        context: IngestionContextPackage | None = None,
    ) -> GraphWritePlan:
        if resolution.clarification is not None:
            raise IngestionValidationError(
                "Cannot build graph write plan while resolution requires clarification."
            )

        decision_by_ref = {decision.candidate_ref: decision for decision in resolution.decisions}
        idempotency_keys: list[str] = []
        nodes_to_create: list[GraphNodeWrite] = []
        relationships_to_create: list[GraphRelationshipWrite] = []
        claims_to_create: list[GraphNodeWrite] = []
        perceptions_to_create: list[GraphNodeWrite] = []
        relationship_contexts_to_create: list[GraphNodeWrite] = []

        for entity in candidate_graph.candidate_entities:
            decision = decision_by_ref.get(entity.local_ref)
            if _decision_type(decision) == ResolutionDecisionType.MATCH_EXISTING:
                continue
            if _decision_type(decision) == ResolutionDecisionType.ASK_CLARIFICATION:
                raise IngestionValidationError(
                    f"Candidate {entity.local_ref} still requires clarification."
                )
            write = self._entity_write(candidate_graph.source_id, entity)
            nodes_to_create.append(write)
            idempotency_keys.append(write.idempotency_key or "")

        for claim in candidate_graph.candidate_claims:
            claim_write = self._claim_write(candidate_graph.source_id, claim)
            claims_to_create.append(claim_write)
            idempotency_keys.append(claim_write.idempotency_key or "")
            for index, about_ref in enumerate(claim.about_refs):
                relationship = self._relationship_write(
                    source_id=candidate_graph.source_id,
                    local_ref=f"{claim.local_ref}_ABOUT_{index + 1:03d}",
                    relationship_type="ABOUT",
                    from_ref=claim.local_ref,
                    to_ref=about_ref,
                    candidate=claim,
                )
                relationships_to_create.append(relationship)
                idempotency_keys.append(relationship.idempotency_key or "")

        for perception in candidate_graph.candidate_perceptions:
            perception_write = self._perception_write(candidate_graph.source_id, perception)
            perceptions_to_create.append(perception_write)
            idempotency_keys.append(perception_write.idempotency_key or "")
            relationship = self._relationship_write(
                source_id=candidate_graph.source_id,
                local_ref=f"{perception.local_ref}_PERCEPTION_OF",
                relationship_type="PERCEPTION_OF",
                from_ref=perception.local_ref,
                to_ref=perception.target_ref,
                candidate=perception,
            )
            relationships_to_create.append(relationship)
            idempotency_keys.append(relationship.idempotency_key or "")

        for context_candidate in candidate_graph.candidate_relationship_contexts:
            context_write = self._relationship_context_write(
                candidate_graph.source_id,
                context_candidate,
            )
            relationship_contexts_to_create.append(context_write)
            idempotency_keys.append(context_write.idempotency_key or "")
            for index, endpoint_ref in enumerate(
                (context_candidate.from_ref, context_candidate.to_ref),
            ):
                relationship = self._relationship_write(
                    source_id=candidate_graph.source_id,
                    local_ref=f"{context_candidate.local_ref}_WITH_{index + 1:03d}",
                    relationship_type="RELATIONSHIP_WITH",
                    from_ref=context_candidate.local_ref,
                    to_ref=endpoint_ref,
                    candidate=context_candidate,
                )
                relationships_to_create.append(relationship)
                idempotency_keys.append(relationship.idempotency_key or "")

        for relationship in candidate_graph.candidate_relationships:
            relationship_write = self._candidate_relationship_write(
                candidate_graph.source_id,
                relationship,
            )
            relationships_to_create.append(relationship_write)
            idempotency_keys.append(relationship_write.idempotency_key or "")

        return GraphWritePlan(
            source_id=candidate_graph.source_id,
            status=GraphWritePlanStatus.DRAFT,
            nodes_to_create=nodes_to_create,
            relationships_to_create=relationships_to_create,
            claims_to_create=claims_to_create,
            perceptions_to_create=perceptions_to_create,
            relationship_contexts_to_create=relationship_contexts_to_create,
            metadata_patches=list(candidate_graph.candidate_metadata_patches),
            evidence_links=list(candidate_graph.evidence_refs),
            idempotency_keys=sorted(key for key in set(idempotency_keys) if key),
            resolution_decisions=list(resolution.decisions),
            metadata={
                "candidate_graph_id": candidate_graph.candidate_graph_id,
                "alias_map": (context.aliases if context else {}),
                "local_ref_resolution": self._local_ref_resolution(resolution),
            },
        )

    def _entity_write(self, source_id: str, candidate: CandidateEntity) -> GraphNodeWrite:
        key = idempotency_key(source_id, "entity", candidate.local_ref, candidate.entity_type)
        properties = _base_properties(source_id, candidate, key)
        properties.update(_entity_display_properties(candidate))
        properties.update(candidate.typed_properties)
        if candidate.description:
            properties["description"] = candidate.description
        if candidate.aliases:
            properties["aliases"] = candidate.aliases
        if candidate.affective_fields:
            properties.update(_affective_properties(candidate.affective_fields))
        if candidate.entity_type in NORMALIZED_NAME_LABELS:
            name = properties.get("display_name") or properties.get("name")
            if isinstance(name, str) and name.strip():
                properties.setdefault("normalized_name", normalize_text(name))
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

    def _local_ref_resolution(self, resolution: ResolutionResult) -> dict[str, str]:
        return {
            decision.candidate_ref: decision.target_entity_id
            for decision in resolution.decisions
            if decision.target_entity_id
        }


def _decision_type(decision: ResolutionDecision | None) -> ResolutionDecisionType:
    if decision is None:
        return ResolutionDecisionType.CREATE
    return ResolutionDecisionType(decision.decision_type)


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


def _relationship_candidate_properties(candidate: CandidateRelationship) -> dict[str, Any]:
    properties = dict(candidate.properties)
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


def _drop_empty(properties: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in properties.items() if value not in (None, "", [])}


_RELATIONSHIP_PROPERTY_FIELDS = {
    "id",
    "description",
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
    "confidence",
    "trust_level",
    "privacy_level",
    "lifecycle_state",
    "source_ids",
    "extraction_run_ids",
    "metadata",
}
