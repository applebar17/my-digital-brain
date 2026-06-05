from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
import re

from my_digital_brain.ingestion.contracts import (
    CandidateClaim,
    CandidateEntity,
    CandidateMemoryGraph,
    CandidateMetadataPatch,
    CandidateOutput,
    CandidatePerception,
    CandidateRelationship,
    CandidateRelationshipContext,
    EvidenceRef,
    ExtractionPlan,
    SourceRecordRef,
)


class CandidateMemoryGraphAssembler:
    """Combine focused extraction outputs into one candidate graph contract."""

    def assemble(
        self,
        source: SourceRecordRef,
        extraction_plan: ExtractionPlan,
        candidates: Sequence[CandidateOutput],
    ) -> CandidateMemoryGraph:
        candidates = _with_unique_local_refs(candidates)
        entities: list[CandidateEntity] = []
        relationships: list[CandidateRelationship] = []
        claims: list[CandidateClaim] = []
        perceptions: list[CandidatePerception] = []
        relationship_contexts: list[CandidateRelationshipContext] = []
        metadata_patches: list[CandidateMetadataPatch] = []

        local_ref_map: dict[str, str] = {}
        evidence_refs: dict[tuple[str, str | None, str | None], EvidenceRef] = {}
        ambiguity_flags: list[str] = []
        missing_fields: list[str] = []

        for candidate in candidates:
            candidate_id = _candidate_id(candidate)
            local_ref_map[candidate.local_ref] = candidate_id
            ambiguity_flags.extend(candidate.ambiguity_flags)

            if isinstance(candidate, CandidateEntity):
                entities.append(candidate)
                missing_fields.extend(candidate.missing_fields)
            elif isinstance(candidate, CandidateRelationship):
                relationships.append(candidate)
            elif isinstance(candidate, CandidateClaim):
                claims.append(candidate)
            elif isinstance(candidate, CandidatePerception):
                perceptions.append(candidate)
            elif isinstance(candidate, CandidateRelationshipContext):
                relationship_contexts.append(candidate)
            elif isinstance(candidate, CandidateMetadataPatch):
                metadata_patches.append(candidate)

            for evidence_ref in candidate.evidence_refs:
                key = (
                    evidence_ref.source_id,
                    evidence_ref.extraction_run_id,
                    evidence_ref.evidence_text,
                )
                evidence_refs[key] = evidence_ref

        return CandidateMemoryGraph(
            source_id=source.source_id,
            extraction_plan_id=extraction_plan.extraction_plan_id,
            candidate_entities=entities,
            candidate_relationships=relationships,
            candidate_claims=claims,
            candidate_perceptions=perceptions,
            candidate_relationship_contexts=relationship_contexts,
            candidate_metadata_patches=metadata_patches,
            local_ref_map=local_ref_map,
            evidence_refs=list(evidence_refs.values()),
            ambiguity_flags=sorted(set(ambiguity_flags)),
            missing_fields=sorted(set(missing_fields)),
        )


def _candidate_id(candidate: CandidateOutput) -> str:
    for field_name in (
        "candidate_id",
        "candidate_relationship_id",
        "candidate_claim_id",
        "candidate_perception_id",
        "candidate_relationship_context_id",
        "patch_id",
    ):
        value = getattr(candidate, field_name, None)
        if isinstance(value, str):
            return value
    return candidate.local_ref


def _with_unique_local_refs(candidates: Sequence[CandidateOutput]) -> list[CandidateOutput]:
    ref_counts = Counter(candidate.local_ref for candidate in candidates)
    if not any(count > 1 for count in ref_counts.values()):
        return list(candidates)

    seen: Counter[str] = Counter()
    remapped_by_task: dict[tuple[str, str], str] = {}
    first_ref: dict[str, str] = {}
    remapped: list[CandidateOutput] = []

    for candidate in candidates:
        original_ref = candidate.local_ref
        task_id = _task_id(candidate)
        seen[original_ref] += 1
        if ref_counts[original_ref] == 1 or seen[original_ref] == 1:
            next_ref = original_ref
        else:
            next_ref = f"{original_ref}_{_task_suffix(task_id, seen[original_ref])}"
        first_ref.setdefault(original_ref, next_ref)
        if task_id:
            remapped_by_task[(task_id, original_ref)] = next_ref
        remapped.append(_copy_with_local_ref(candidate, next_ref, original_ref))

    return [
        _copy_with_rewritten_refs(candidate, remapped_by_task, first_ref)
        for candidate in remapped
    ]


def _copy_with_local_ref(
    candidate: CandidateOutput,
    next_ref: str,
    original_ref: str,
) -> CandidateOutput:
    if next_ref == original_ref:
        return candidate
    metadata = {
        **candidate.metadata,
        "original_local_ref": original_ref,
        "local_ref_normalization": "duplicate_remapped",
    }
    return candidate.model_copy(update={"local_ref": next_ref, "metadata": metadata})


def _copy_with_rewritten_refs(
    candidate: CandidateOutput,
    remapped_by_task: dict[tuple[str, str], str],
    first_ref: dict[str, str],
) -> CandidateOutput:
    task_id = _task_id(candidate)

    def rewrite(ref: str) -> str:
        if not ref.startswith("CANDIDATE_"):
            return ref
        if task_id and (task_id, ref) in remapped_by_task:
            return remapped_by_task[(task_id, ref)]
        return first_ref.get(ref, ref)

    if isinstance(candidate, CandidateRelationship):
        return candidate.model_copy(
            update={
                "from_ref": rewrite(candidate.from_ref),
                "to_ref": rewrite(candidate.to_ref),
            },
        )
    if isinstance(candidate, CandidateClaim):
        return candidate.model_copy(
            update={"about_refs": [rewrite(ref) for ref in candidate.about_refs]},
        )
    if isinstance(candidate, CandidatePerception):
        return candidate.model_copy(update={"target_ref": rewrite(candidate.target_ref)})
    if isinstance(candidate, CandidateRelationshipContext):
        return candidate.model_copy(
            update={
                "from_ref": rewrite(candidate.from_ref),
                "to_ref": rewrite(candidate.to_ref),
            },
        )
    if isinstance(candidate, CandidateMetadataPatch):
        return candidate.model_copy(update={"target_ref": rewrite(candidate.target_ref)})
    return candidate


def _task_id(candidate: CandidateOutput) -> str:
    value = candidate.metadata.get("task_id")
    return str(value) if value else ""


def _task_suffix(task_id: str, occurrence: int) -> str:
    if task_id:
        sanitized = re.sub(r"[^A-Za-z0-9]+", "", task_id).upper()
        if sanitized:
            return f"TASK_{sanitized[:8]}_{occurrence:03d}"
    return f"DUP_{occurrence:03d}"
