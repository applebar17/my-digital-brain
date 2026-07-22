from __future__ import annotations

from collections.abc import Sequence

from my_digital_brain.ingestion.contracts import (
    CandidateClaim,
    CandidateEntity,
    CandidateMemoryGraph,
    CandidateMetadataPatch,
    CandidateOutput,
    CandidatePerception,
    CandidateProfileMemory,
    CandidateRelationship,
    CandidateRelationshipContext,
    EvidenceRef,
    ExtractionPlan,
    MemoryLog,
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
        candidates = list(candidates)
        entities: list[CandidateEntity] = []
        relationships: list[CandidateRelationship] = []
        claims: list[CandidateClaim] = []
        perceptions: list[CandidatePerception] = []
        relationship_contexts: list[CandidateRelationshipContext] = []
        metadata_patches: list[CandidateMetadataPatch] = []
        profile_memories: list[CandidateProfileMemory] = []
        memory_logs: list[MemoryLog] = []

        local_ref_map: dict[str, str] = {}
        evidence_refs: dict[tuple[str, str | None, str | None], EvidenceRef] = {}
        ambiguity_flags: list[str] = []
        missing_fields: list[str] = []

        for candidate in candidates:
            candidate_id = _candidate_id(candidate)
            local_ref_map[candidate.local_ref] = candidate_id
            ambiguity_flags.extend(getattr(candidate, "ambiguity_flags", []))

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
            elif isinstance(candidate, CandidateProfileMemory):
                profile_memories.append(candidate)
            elif isinstance(candidate, MemoryLog):
                memory_logs.append(candidate)

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
            candidate_profile_memories=profile_memories,
            memory_logs=memory_logs,
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
        "candidate_id",
        "memory_log_id",
    ):
        value = getattr(candidate, field_name, None)
        if isinstance(value, str):
            return value
    return candidate.local_ref
