from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from my_digital_brain.graph.exceptions import GraphValidationError
from my_digital_brain.graph.registry import validate_node_label, validate_relationship_type
from my_digital_brain.ingestion.contracts import (
    CandidateBase,
    CandidateMemoryGraph,
    GraphNodeWrite,
    GraphRelationshipWrite,
    GraphWritePlan,
    ValidationIssue,
    ValidationResult,
)


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

        for index, patch in enumerate(candidate_graph.candidate_metadata_patches):
            prefix = f"candidate_metadata_patches[{index}]"
            self._validate_candidate_ref(
                patch.target_ref,
                f"{prefix}.target_ref",
                known_refs,
                issues,
            )
            self._validate_evidence(patch, prefix, issues)

        return ValidationResult.from_issues(issues)

    def validate_write_plan(self, write_plan: GraphWritePlan) -> ValidationResult:
        issues: list[ValidationIssue] = []
        node_writes = [
            *write_plan.nodes_to_create,
            *write_plan.nodes_to_update,
            *write_plan.claims_to_create,
            *write_plan.perceptions_to_create,
            *write_plan.relationship_contexts_to_create,
        ]
        local_refs = {write.local_ref for write in node_writes}

        self._validate_write_ref_uniqueness(node_writes, issues)

        for index, write in enumerate(node_writes):
            self._validate_label(write.label, f"node_writes[{index}]", issues)

        relationship_writes = [
            *write_plan.relationships_to_create,
            *write_plan.relationships_to_update,
        ]
        for index, write in enumerate(relationship_writes):
            prefix = f"relationship_writes[{index}]"
            self._validate_relationship_type(write.relationship_type, prefix, issues)
            self._validate_write_endpoint(write.from_ref, f"{prefix}.from_ref", local_refs, issues)
            self._validate_write_endpoint(write.to_ref, f"{prefix}.to_ref", local_refs, issues)

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
                    f"{field_path}.entity_type",
                    str(exc),
                    "unsupported_node_label",
                    {"label": label},
                ),
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

    def _validate_local_ref_uniqueness(
        self,
        candidate_graph: CandidateMemoryGraph,
        issues: list[ValidationIssue],
    ) -> None:
        refs = [candidate.local_ref for candidate in _all_candidates(candidate_graph)]
        for ref, count in Counter(refs).items():
            if count > 1:
                issues.append(
                    _issue(
                        "local_ref",
                        f"Duplicate local_ref '{ref}'. Candidate refs must be unique.",
                        "duplicate_local_ref",
                        {"ref": ref, "count": count},
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
    return refs


def _all_candidates(candidate_graph: CandidateMemoryGraph) -> list[CandidateBase]:
    return [
        *candidate_graph.candidate_entities,
        *candidate_graph.candidate_relationships,
        *candidate_graph.candidate_claims,
        *candidate_graph.candidate_perceptions,
        *candidate_graph.candidate_relationship_contexts,
        *candidate_graph.candidate_metadata_patches,
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
