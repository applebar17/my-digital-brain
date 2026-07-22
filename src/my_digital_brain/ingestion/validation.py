from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from my_digital_brain.graph.constants import OWNER_ALIAS
from my_digital_brain.graph.exceptions import GraphValidationError
from my_digital_brain.graph.registry import validate_node_label, validate_relationship_type
from my_digital_brain.ingestion.contracts import (
    CandidateBase,
    CandidateMemoryGraph,
    GraphNodeWrite,
    GraphWritePlan,
    ValidationIssue,
    ValidationResult,
)
from my_digital_brain.ingestion.reference_registry import RunReferenceRegistry


class IngestionValidator:
    """Validate ingestion contracts before they can become graph writes."""

    def validate_candidate_graph(self, candidate_graph: CandidateMemoryGraph) -> ValidationResult:
        issues: list[ValidationIssue] = []
        known_refs = _candidate_refs(candidate_graph)

        self._validate_local_ref_uniqueness(candidate_graph, issues)

        for index, entity in enumerate(candidate_graph.candidate_entities):
            self._validate_label(entity.entity_type, f"candidate_entities[{index}]", issues)
            self._validate_evidence(
                entity,
                f"candidate_entities[{index}]",
                issues,
            )
            self._validate_owner_entity(entity, f"candidate_entities[{index}]", issues)

        for index, profile in enumerate(candidate_graph.candidate_profile_memories):
            prefix = f"candidate_profile_memories[{index}]"
            if profile.owner_ref != OWNER_ALIAS:
                issues.append(
                    _issue(
                        f"{prefix}.owner_ref",
                        "Owner profile proposals must use OWNER.",
                        "invalid_owner_ref",
                        {"owner_ref": profile.owner_ref},
                    )
                )
            if profile.assertion_mode == "inferred" and not profile.requires_confirmation:
                issues.append(
                    _issue(
                        f"{prefix}.requires_confirmation",
                        "Inferred owner traits require confirmation.",
                        "inferred_owner_trait_not_confirmed",
                    )
                )
            self._validate_evidence(profile, prefix, issues)

        for index, relationship in enumerate(candidate_graph.candidate_relationships):
            prefix = f"candidate_relationships[{index}]"
            self._validate_relationship_type(relationship.relationship_type, prefix, issues)
            self._validate_candidate_ref(
                relationship.from_ref,
                f"{prefix}.from_ref",
                known_refs,
                issues,
            )
            self._validate_candidate_ref(
                relationship.to_ref,
                f"{prefix}.to_ref",
                known_refs,
                issues,
            )
            self._validate_evidence(relationship, prefix, issues)

        for index, claim in enumerate(candidate_graph.candidate_claims):
            prefix = f"candidate_claims[{index}]"
            for ref_index, ref in enumerate(claim.about_refs):
                self._validate_candidate_ref(
                    ref,
                    f"{prefix}.about_refs[{ref_index}]",
                    known_refs,
                    issues,
                )
            self._validate_evidence(claim, prefix, issues)

        for index, perception in enumerate(candidate_graph.candidate_perceptions):
            prefix = f"candidate_perceptions[{index}]"
            self._validate_candidate_ref(
                perception.target_ref,
                f"{prefix}.target_ref",
                known_refs,
                issues,
            )
            self._validate_evidence(perception, prefix, issues)

        for index, context in enumerate(candidate_graph.candidate_relationship_contexts):
            prefix = f"candidate_relationship_contexts[{index}]"
            self._validate_candidate_ref(context.from_ref, f"{prefix}.from_ref", known_refs, issues)
            self._validate_candidate_ref(context.to_ref, f"{prefix}.to_ref", known_refs, issues)
            self._validate_evidence(context, prefix, issues)

        for index, memory_log in enumerate(candidate_graph.memory_logs):
            prefix = f"memory_logs[{index}]"
            self._validate_memory_log(memory_log, prefix, known_refs, issues)

        for index, patch in enumerate(candidate_graph.candidate_metadata_patches):
            prefix = f"candidate_metadata_patches[{index}]"
            self._validate_candidate_ref(
                patch.target_ref,
                f"{prefix}.target_ref",
                known_refs,
                issues,
            )
            self._validate_evidence(patch, prefix, issues)
            if patch.target_ref == OWNER_ALIAS and patch.path in {
                "is_owner",
                "personality",
                "preference",
                "goal",
                "work_style",
                "profile_key",
                "stability",
                "visibility",
            }:
                issues.append(
                    _issue(
                        f"{prefix}.path",
                        (
                            "LLM proposals cannot patch owner identity or place profile data "
                            "on Person."
                        ),
                        "owner_profile_patch_forbidden",
                    )
                )

        return ValidationResult.from_issues(issues)

    def validate_write_plan(self, write_plan: GraphWritePlan) -> ValidationResult:
        issues: list[ValidationIssue] = []
        node_writes = [
            *write_plan.nodes_to_create,
            *write_plan.nodes_to_update,
            *write_plan.claims_to_create,
            *write_plan.perceptions_to_create,
            *write_plan.relationship_contexts_to_create,
            *write_plan.memory_logs_to_create,
            *write_plan.profile_memories_to_create,
        ]
        local_refs = {write.local_ref for write in node_writes}
        local_refs.update((write_plan.metadata or {}).get("local_ref_resolution", {}))

        self._validate_write_ref_uniqueness(node_writes, issues)

        for index, write in enumerate(node_writes):
            self._validate_label(write.label, f"node_writes[{index}]", issues)
            self._validate_owner_properties(write, f"node_writes[{index}]", issues)

        relationship_writes = [
            *write_plan.relationships_to_create,
            *write_plan.relationships_to_update,
        ]
        metadata = write_plan.metadata or {}
        owner_alias_map = metadata.get("alias_map", {})
        registry_snapshot = metadata.get("reference_registry_snapshot") or {}
        if registry_snapshot:
            try:
                owner_alias_map = RunReferenceRegistry.from_snapshot(
                    registry_snapshot,
                ).backend_alias_map()
            except ValueError as exc:
                issues.append(
                    _issue(
                        "metadata.reference_registry_snapshot",
                        str(exc),
                        "invalid_reference_registry_snapshot",
                    )
                )
        for index, write in enumerate(relationship_writes):
            prefix = f"relationship_writes[{index}]"
            self._validate_relationship_type(write.relationship_type, prefix, issues)
            self._validate_write_endpoint(write.from_ref, f"{prefix}.from_ref", local_refs, issues)
            self._validate_write_endpoint(write.to_ref, f"{prefix}.to_ref", local_refs, issues)
            if write.relationship_type == "DESCRIBES_USER" and write.to_ref != OWNER_ALIAS:
                issues.append(
                    _issue(
                        f"{prefix}.to_ref",
                        "DESCRIBES_USER must target OWNER.",
                        "profile_relationship_owner_required",
                        {"to_ref": write.to_ref},
                    )
                )
            if OWNER_ALIAS in {write.from_ref, write.to_ref} and OWNER_ALIAS not in owner_alias_map:
                issues.append(
                    _issue(
                        f"relationship_writes[{index}]",
                        "Owner relationships require a backend OWNER alias mapping.",
                        "missing_owner_alias_mapping",
                    )
                )

        return ValidationResult.from_issues(issues)

    def _validate_label(
        self,
        label: str,
        field_path: str,
        issues: list[ValidationIssue],
    ) -> None:
        try:
            validate_node_label(label)
        except GraphValidationError as exc:
            issues.append(
                _issue(
                    f"{field_path}.label",
                    str(exc),
                    "unsupported_node_label",
                    {"label": label},
                ),
            )

    def _validate_owner_entity(
        self, entity: Any, field_path: str, issues: list[ValidationIssue]
    ) -> None:
        if entity.local_ref == OWNER_ALIAS:
            issues.append(
                _issue(
                    f"{field_path}.local_ref",
                    "OWNER is an existing node and cannot be created as a Person candidate.",
                    "owner_duplicate_candidate",
                )
            )
        if entity.entity_type == "Person" and entity.typed_properties.get("is_owner") is True:
            issues.append(
                _issue(
                    f"{field_path}.typed_properties.is_owner",
                    "LLM graph proposals cannot create an owner Person.",
                    "owner_creation_forbidden",
                )
            )
        if entity.entity_type != "Person" and "is_owner" in entity.typed_properties:
            issues.append(
                _issue(
                    f"{field_path}.typed_properties.is_owner",
                    "is_owner is valid only on Person candidates.",
                    "invalid_owner_property",
                )
            )

    def _validate_owner_properties(
        self,
        write: GraphNodeWrite,
        field_path: str,
        issues: list[ValidationIssue],
    ) -> None:
        if write.label == "Person" and write.properties.get("is_owner") is True:
            issues.append(
                _issue(
                    f"{field_path}.properties.is_owner",
                    "Normal graph writes cannot create an owner Person.",
                    "owner_creation_forbidden",
                )
            )
        if write.label != "Person" and "is_owner" in write.properties:
            issues.append(
                _issue(
                    f"{field_path}.properties.is_owner",
                    "is_owner is valid only on Person nodes.",
                    "invalid_owner_property",
                )
            )
        if write.label == "Person" and any(
            key in write.properties
            for key in (
                "profile_key",
                "stability",
                "visibility",
                "personality",
                "preference",
                "goal",
            )
        ):
            issues.append(
                _issue(
                    f"{field_path}.properties",
                    "Stable owner profile data must be stored as ProfileMemory.",
                    "profile_data_on_person_forbidden",
                )
            )

    def _validate_relationship_type(
        self,
        relationship_type: str,
        field_path: str,
        issues: list[ValidationIssue],
    ) -> None:
        try:
            validate_relationship_type(relationship_type)
        except GraphValidationError as exc:
            issues.append(
                _issue(
                    f"{field_path}.relationship_type",
                    str(exc),
                    "unsupported_relationship_type",
                    {"relationship_type": relationship_type},
                ),
            )

    def _validate_candidate_ref(
        self,
        ref: str,
        field_path: str,
        known_refs: set[str],
        issues: list[ValidationIssue],
    ) -> None:
        if _is_candidate_ref(ref) and ref not in known_refs:
            issues.append(
                _issue(
                    field_path,
                    (
                        f"Unknown candidate reference '{ref}'. Use one of the current "
                        "candidate local refs or a graph alias provided in context."
                    ),
                    "unknown_candidate_ref",
                    {"ref": ref, "known_refs": sorted(known_refs)},
                ),
            )

    def _validate_write_endpoint(
        self,
        ref: str,
        field_path: str,
        local_refs: set[str],
        issues: list[ValidationIssue],
    ) -> None:
        if _is_candidate_ref(ref) and ref not in local_refs:
            issues.append(
                _issue(
                    field_path,
                    (
                        f"Unknown write endpoint '{ref}'. A candidate endpoint must "
                        "refer to a node write in the same plan."
                    ),
                    "unknown_write_endpoint",
                    {"ref": ref, "known_refs": sorted(local_refs)},
                ),
            )

    def _validate_evidence(
        self,
        candidate: CandidateBase,
        field_path: str,
        issues: list[ValidationIssue],
    ) -> None:
        if candidate.source_refs or candidate.evidence_refs:
            return
        issues.append(
            _issue(
                field_path,
                (
                    "Candidate has no source_refs or evidence_refs. Memory writes must "
                    "remain provenance-backed so later retrieval can explain them."
                ),
                "missing_candidate_evidence",
                {"local_ref": candidate.local_ref},
            ),
        )

    def _validate_memory_log(
        self,
        memory_log: Any,
        field_path: str,
        known_refs: set[str],
        issues: list[ValidationIssue],
    ) -> None:
        if not (memory_log.local_ref or "").strip():
            issues.append(
                _issue(
                    f"{field_path}.local_ref",
                    "MemoryLog writes require a stable local_ref.",
                    "missing_memory_log_local_ref",
                    {"memory_log_id": memory_log.memory_log_id},
                ),
            )
        if not memory_log.log_text.strip():
            issues.append(
                _issue(
                    f"{field_path}.log_text",
                    "MemoryLog requires non-empty log_text.",
                    "missing_memory_log_text",
                    {"local_ref": memory_log.local_ref},
                ),
            )
        if not (memory_log.source_refs or memory_log.evidence_refs):
            issues.append(
                _issue(
                    field_path,
                    (
                        "MemoryLog has no source_refs or evidence_refs. Memory writes "
                        "must remain provenance-backed so later retrieval can explain them."
                    ),
                    "missing_memory_log_evidence",
                    {"local_ref": memory_log.local_ref},
                ),
            )

        host_links = [
            link for link in memory_log.links if link.relationship_type == "HAS_MEMORY_LOG"
        ]
        host_ids = set(memory_log.host_target_ids)
        host_ids.update(link.target_id for link in host_links)
        if memory_log.primary_host_target_id:
            host_ids.add(memory_log.primary_host_target_id)
        if not host_ids:
            issues.append(
                _issue(
                    f"{field_path}.links",
                    "MemoryLog requires at least one HAS_MEMORY_LOG host target.",
                    "missing_memory_log_host",
                    {"local_ref": memory_log.local_ref},
                ),
            )
        primary_count = sum(1 for link in host_links if link.primary)
        if primary_count > 1:
            issues.append(
                _issue(
                    f"{field_path}.links",
                    "MemoryLog can have at most one primary HAS_MEMORY_LOG link.",
                    "duplicate_memory_log_primary_host",
                    {"local_ref": memory_log.local_ref},
                ),
            )
        if len(host_ids) > 1 and primary_count != 1 and not memory_log.primary_host_target_id:
            issues.append(
                _issue(
                    f"{field_path}.links",
                    "MemoryLog with multiple host targets requires one primary host.",
                    "missing_memory_log_primary_host",
                    {"local_ref": memory_log.local_ref},
                ),
            )

        for host_index, ref in enumerate(memory_log.host_target_ids):
            self._validate_candidate_ref(
                ref,
                f"{field_path}.host_target_ids[{host_index}]",
                known_refs,
                issues,
            )
        if memory_log.primary_host_target_id:
            self._validate_candidate_ref(
                memory_log.primary_host_target_id,
                f"{field_path}.primary_host_target_id",
                known_refs,
                issues,
            )
        for involved_index, ref in enumerate(memory_log.involved_target_ids):
            self._validate_candidate_ref(
                ref,
                f"{field_path}.involved_target_ids[{involved_index}]",
                known_refs,
                issues,
            )

        for link_index, link in enumerate(memory_log.links):
            prefix = f"{field_path}.links[{link_index}]"
            self._validate_relationship_type(link.relationship_type, prefix, issues)
            self._validate_candidate_ref(link.target_id, f"{prefix}.target_id", known_refs, issues)
            if link.relationship_type == "HAS_MEMORY_LOG" and not link.target_id:
                issues.append(
                    _issue(
                        f"{prefix}.target_id",
                        "HAS_MEMORY_LOG requires a target id or candidate ref.",
                        "missing_memory_log_link_target",
                        {"local_ref": memory_log.local_ref},
                    ),
                )

    def _validate_local_ref_uniqueness(
        self,
        candidate_graph: CandidateMemoryGraph,
        issues: list[ValidationIssue],
    ) -> None:
        refs = [candidate.local_ref for candidate in _all_candidates(candidate_graph)]
        refs.extend(
            memory_log.local_ref
            for memory_log in candidate_graph.memory_logs
            if memory_log.local_ref
        )
        for ref, count in Counter(refs).items():
            if count > 1:
                issues.append(
                    _issue(
                        "local_ref",
                        (
                            f"Candidate ID '{ref}' is already present in this session. "
                            "Assigned candidate IDs: "
                            f"{', '.join(sorted(set(refs)))}. Use a unique candidate ID."
                        ),
                        "duplicate_local_ref",
                        {
                            "ref": ref,
                            "count": count,
                            "assigned_refs": sorted(set(refs)),
                        },
                    ),
                )

    def _validate_write_ref_uniqueness(
        self,
        writes: Iterable[GraphNodeWrite],
        issues: list[ValidationIssue],
    ) -> None:
        refs = [write.local_ref for write in writes]
        for ref, count in Counter(refs).items():
            if count > 1:
                issues.append(
                    _issue(
                        "local_ref",
                        f"Duplicate write local_ref '{ref}'. Write refs must be unique.",
                        "duplicate_write_ref",
                        {"ref": ref, "count": count},
                    ),
                )


def _candidate_refs(candidate_graph: CandidateMemoryGraph) -> set[str]:
    refs = set(candidate_graph.local_ref_map)
    refs.update(candidate.local_ref for candidate in _all_candidates(candidate_graph))
    refs.update(
        memory_log.local_ref for memory_log in candidate_graph.memory_logs if memory_log.local_ref
    )
    return refs


def _all_candidates(candidate_graph: CandidateMemoryGraph) -> list[CandidateBase]:
    return [
        *candidate_graph.candidate_entities,
        *candidate_graph.candidate_relationships,
        *candidate_graph.candidate_claims,
        *candidate_graph.candidate_perceptions,
        *candidate_graph.candidate_relationship_contexts,
        *candidate_graph.candidate_metadata_patches,
        *candidate_graph.candidate_profile_memories,
    ]


def _is_candidate_ref(ref: str) -> bool:
    return ref.startswith("CANDIDATE_")


def _issue(
    field_path: str,
    message: str,
    code: str,
    details: dict[str, Any] | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        field_path=field_path,
        message=message,
        code=code,
        details=details or {},
    )
