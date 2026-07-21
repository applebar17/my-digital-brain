from __future__ import annotations

from typing import Any

from my_digital_brain.graph.constants import AFFECTIVE_FIELD_NAMES, NORMALIZED_NAME_LABELS
from my_digital_brain.graph.constants import OWNER_ALIAS
from my_digital_brain.graph.models import node_model_for_label
from my_digital_brain.graph.utils import normalize_text
from my_digital_brain.ingestion.contracts import (
    AffectiveFields,
    CandidateBase,
    CandidateClaim,
    CandidateEntity,
    CandidateMemoryGraph,
    CandidatePerception,
    CandidateProfileMemory,
    CandidateRelationship,
    CandidateRelationshipContext,
    EvidenceRef,
    GraphNodeWrite,
    GraphRelationshipWrite,
    GraphWritePlan,
    IngestionContextPackage,
    MemoryLog,
    MemoryLogLink,
    ResolutionDecision,
    ResolutionResult,
    ResolutionStep,
    ResolutionToolAction,
    TemporalScope,
)
from my_digital_brain.ingestion.enums import GraphWritePlanStatus, ResolutionDecisionType
from my_digital_brain.ingestion.exceptions import IngestionValidationError
from my_digital_brain.ingestion.idempotency import deterministic_uuid, idempotency_key
from my_digital_brain.ingestion.resolution_write_actions import ResolutionWriteActions


def _required_action(
    actions: ResolutionWriteActions | None,
    step: ResolutionStep,
    candidate_ref: str,
) -> ResolutionToolAction | None:
    if actions is None:
        return None
    action = actions.for_ref(step, candidate_ref)
    if action is None:
        raise IngestionValidationError(
            f"No validated {step.value} resolution action exists for {candidate_ref}."
        )
    return action


class GraphWritePlanBuilder:
    """Build deterministic, backend-owned graph write commands."""

    def build(
        self,
        candidate_graph: CandidateMemoryGraph,
        resolution: ResolutionResult,
        context: IngestionContextPackage | None = None,
    ) -> GraphWritePlan:
        if resolution.clarifications:
            raise IngestionValidationError(
                "Cannot build graph write plan while resolution requires clarification."
            )
        if candidate_graph.candidate_profile_memories and (
            context is None or OWNER_ALIAS not in context.aliases
        ):
            raise IngestionValidationError(
                "Profile memory writes require the backend OWNER alias mapping."
            )

        decision_by_ref = {decision.candidate_ref: decision for decision in resolution.decisions}
        resolution_actions = ResolutionWriteActions.from_result(resolution)
        idempotency_keys: list[str] = []
        nodes_to_create: list[GraphNodeWrite] = []
        relationships_to_create: list[GraphRelationshipWrite] = []
        claims_to_create: list[GraphNodeWrite] = []
        perceptions_to_create: list[GraphNodeWrite] = []
        relationship_contexts_to_create: list[GraphNodeWrite] = []
        nodes_to_update: list[GraphNodeWrite] = []
        memory_logs_to_create: list[GraphNodeWrite] = []
        profile_memories_to_create: list[GraphNodeWrite] = []
        relationships_to_update: list[GraphRelationshipWrite] = []
        planned_ref_ids = self._local_ref_resolution(resolution)

        for entity in candidate_graph.candidate_entities:
            decision = decision_by_ref.get(entity.local_ref)
            if _decision_type(decision) == ResolutionDecisionType.MATCH_EXISTING:
                continue
            if _decision_type(decision) in {
                ResolutionDecisionType.REJECT,
                ResolutionDecisionType.KEEP_PENDING,
            }:
                continue
            if _decision_type(decision) == ResolutionDecisionType.ASK_CLARIFICATION:
                raise IngestionValidationError(
                    f"Candidate {entity.local_ref} still requires clarification."
                )
            write = self._entity_write(candidate_graph.source_id, entity)
            nodes_to_create.append(write)
            planned_ref_ids[entity.local_ref] = str(write.properties["id"])
            idempotency_keys.append(write.idempotency_key or "")

        for claim in candidate_graph.candidate_claims:
            claim_write = self._claim_write(candidate_graph.source_id, claim)
            claims_to_create.append(claim_write)
            planned_ref_ids[claim.local_ref] = str(claim_write.properties["id"])
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
            planned_ref_ids[perception.local_ref] = str(perception_write.properties["id"])
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
            action = _required_action(
                resolution_actions,
                ResolutionStep.RELATIONSHIP,
                context_candidate.local_ref,
            )
            if ResolutionWriteActions.is_skip(action):
                continue
            context_write = self._relationship_context_write(
                candidate_graph.source_id,
                context_candidate,
            )
            if ResolutionWriteActions.is_update(action):
                nodes_to_update.append(ResolutionWriteActions.node_update(context_write, action))
            else:
                relationship_contexts_to_create.append(context_write)
            planned_ref_ids[context_candidate.local_ref] = str(context_write.properties["id"])
            idempotency_keys.append(context_write.idempotency_key or "")
            if action is not None and ResolutionWriteActions.is_update(action):
                continue
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

        for memory_log in candidate_graph.memory_logs:
            action = _required_action(
                resolution_actions,
                ResolutionStep.MEMORY,
                memory_log.local_ref or memory_log.memory_log_id,
            )
            if ResolutionWriteActions.is_skip(action):
                continue
            memory_log_write = self._memory_log_write(
                candidate_graph.source_id,
                memory_log,
                planned_ref_ids,
            )
            if ResolutionWriteActions.is_update(action):
                nodes_to_update.append(ResolutionWriteActions.node_update(memory_log_write, action))
            else:
                memory_logs_to_create.append(memory_log_write)
            planned_ref_ids[memory_log_write.local_ref] = str(memory_log_write.properties["id"])
            idempotency_keys.append(memory_log_write.idempotency_key or "")
            if not ResolutionWriteActions.is_update(action):
                for index, link in enumerate(_memory_log_links(memory_log)):
                    relationship = self._memory_log_relationship_write(
                        source_id=candidate_graph.source_id,
                        memory_log=memory_log,
                        link=link,
                        index=index,
                    )
                    relationships_to_create.append(relationship)
                    idempotency_keys.append(relationship.idempotency_key or "")

        for profile in candidate_graph.candidate_profile_memories:
            action = _required_action(
                resolution_actions,
                ResolutionStep.MEMORY,
                profile.local_ref,
            )
            if ResolutionWriteActions.is_skip(action):
                continue
            profile_write = self._profile_memory_write(candidate_graph.source_id, profile)
            if ResolutionWriteActions.is_update(action):
                nodes_to_update.append(ResolutionWriteActions.node_update(profile_write, action))
            else:
                profile_memories_to_create.append(profile_write)
            planned_ref_ids[profile.local_ref] = str(profile_write.properties["id"])
            idempotency_keys.append(profile_write.idempotency_key or "")
            if not ResolutionWriteActions.is_update(action):
                relationship = self._relationship_write(
                    source_id=candidate_graph.source_id,
                    local_ref=f"{profile.local_ref}_DESCRIBES_USER",
                    relationship_type="DESCRIBES_USER",
                    from_ref=profile.local_ref,
                    to_ref="OWNER",
                    candidate=profile,
                )
                relationships_to_create.append(relationship)
                idempotency_keys.append(relationship.idempotency_key or "")

        for relationship in candidate_graph.candidate_relationships:
            action = _required_action(
                resolution_actions,
                ResolutionStep.RELATIONSHIP,
                relationship.local_ref,
            )
            if ResolutionWriteActions.is_skip(action):
                continue
            relationship_write = self._candidate_relationship_write(
                candidate_graph.source_id,
                relationship,
            )
            if ResolutionWriteActions.is_update(action):
                relationships_to_update.append(
                    ResolutionWriteActions.relationship_endpoints(relationship_write, action)
                )
            else:
                relationships_to_create.append(relationship_write)
            idempotency_keys.append(relationship_write.idempotency_key or "")

        return GraphWritePlan(
            source_id=candidate_graph.source_id,
            status=GraphWritePlanStatus.DRAFT,
            nodes_to_create=nodes_to_create,
            nodes_to_update=nodes_to_update,
            relationships_to_create=relationships_to_create,
            relationships_to_update=relationships_to_update,
            claims_to_create=claims_to_create,
            perceptions_to_create=perceptions_to_create,
            relationship_contexts_to_create=relationship_contexts_to_create,
            memory_logs_to_create=memory_logs_to_create,
            profile_memories_to_create=profile_memories_to_create,
            metadata_patches=list(candidate_graph.candidate_metadata_patches),
            evidence_links=list(candidate_graph.evidence_refs),
            idempotency_keys=sorted(key for key in set(idempotency_keys) if key),
            resolution_decisions=list(resolution.decisions),
            metadata={
                "candidate_graph_id": candidate_graph.candidate_graph_id,
                "alias_map": (context.aliases if context else {}),
                "reference_registry_snapshot": (
                    context.reference_registry_snapshot if context else {}
                ),
                "local_ref_resolution": self._local_ref_resolution(resolution),
            },
        )

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
