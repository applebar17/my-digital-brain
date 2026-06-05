from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from my_digital_brain.ingestion.contracts import (
    CandidateClaim,
    CandidateEntity,
    CandidateMetadataPatch,
    CandidateOutput,
    CandidatePerception,
    CandidateRelationship,
    CandidateRelationshipContext,
    EvidenceRef,
    ExtractionTask,
    Mention,
    MentionScan,
    SourceRecordRef,
)
from my_digital_brain.ingestion.contracts.drafts import (
    CandidateBaseDraft,
    CandidateClaimDraft,
    CandidateClaimDraftBatch,
    CandidateEntityDraft,
    CandidateEntityDraftBatch,
    CandidateMetadataPatchDraft,
    CandidateMetadataPatchDraftBatch,
    CandidateOutputDraft,
    CandidatePerceptionDraft,
    CandidatePerceptionDraftBatch,
    CandidateRelationshipContextDraft,
    CandidateRelationshipContextDraftBatch,
    CandidateRelationshipDraft,
    CandidateRelationshipDraftBatch,
    EvidenceSpanDraft,
    MentionDraft,
    MentionScanDraft,
    PropertyDraft,
)
from my_digital_brain.ingestion.normalization import (
    canonical_node_label,
    canonical_relationship_type,
)


def enrich_mention_scan(draft: MentionScanDraft, source: SourceRecordRef) -> MentionScan:
    return MentionScan(
        source_id=source.source_id,
        mentions=[_enrich_mention(mention) for mention in draft.mentions],
        metadata={"schema_layer": "backend_enriched"},
    )


def enrich_candidate_batch(
    draft_batch: Any,
    source: SourceRecordRef,
    task: ExtractionTask,
) -> list[CandidateOutput]:
    if isinstance(draft_batch, CandidateEntityDraftBatch):
        return [_enrich_entity(candidate, source, task) for candidate in draft_batch.candidates]
    if isinstance(draft_batch, CandidateRelationshipDraftBatch):
        return [
            _enrich_relationship(candidate, source, task)
            for candidate in draft_batch.candidates
        ]
    if isinstance(draft_batch, CandidateClaimDraftBatch):
        return [_enrich_claim(candidate, source, task) for candidate in draft_batch.candidates]
    if isinstance(draft_batch, CandidatePerceptionDraftBatch):
        return [
            _enrich_perception(candidate, source, task)
            for candidate in draft_batch.candidates
        ]
    if isinstance(draft_batch, CandidateRelationshipContextDraftBatch):
        return [
            _enrich_relationship_context(candidate, source, task)
            for candidate in draft_batch.candidates
        ]
    if isinstance(draft_batch, CandidateMetadataPatchDraftBatch):
        return [
            _enrich_metadata_patch(candidate, source, task)
            for candidate in draft_batch.candidates
        ]
    raise TypeError(f"Unsupported candidate draft batch: {type(draft_batch).__name__}")


def property_suggestions_to_dict(
    suggestions: Sequence[PropertyDraft],
) -> dict[str, Any]:
    return {
        suggestion.key: _coerce_property_value(suggestion.value_text, suggestion.value_kind)
        for suggestion in suggestions
        if suggestion.key
    }


def _enrich_mention(draft: MentionDraft) -> Mention:
    return Mention(
        kind=draft.kind,
        text=draft.text,
        evidence_text=draft.evidence_text,
        span_start=draft.span_start,
        span_end=draft.span_end,
        possible_normalized_value=draft.possible_normalized_value,
        ambiguity_hint=draft.ambiguity_hint,
    )


def _enrich_entity(
    draft: CandidateEntityDraft,
    source: SourceRecordRef,
    task: ExtractionTask,
) -> CandidateEntity:
    entity_type = canonical_node_label(draft.entity_type)
    payload = _base_candidate_payload(draft, source, task)
    if entity_type != draft.entity_type:
        payload["metadata"]["original_entity_type"] = draft.entity_type
        payload["metadata"]["normalized_entity_type"] = entity_type
    return CandidateEntity(
        **payload,
        entity_type=entity_type,
        display_name=draft.display_name,
        description=draft.description,
        aliases=list(draft.aliases),
        typed_properties=property_suggestions_to_dict(draft.property_suggestions),
        affective_fields=draft.affective_fields,
        missing_fields=list(draft.missing_fields),
    )


def _enrich_relationship(
    draft: CandidateRelationshipDraft,
    source: SourceRecordRef,
    task: ExtractionTask,
) -> CandidateRelationship:
    relationship_type = canonical_relationship_type(draft.relationship_type)
    payload = _base_candidate_payload(draft, source, task)
    if relationship_type != draft.relationship_type:
        payload["metadata"]["original_relationship_type"] = draft.relationship_type
        payload["metadata"]["normalized_relationship_type"] = relationship_type
    return CandidateRelationship(
        **payload,
        relationship_type=relationship_type,
        from_ref=draft.from_ref,
        to_ref=draft.to_ref,
        relationship_kind=draft.relationship_kind,
        relationship_detail=draft.relationship_detail,
        properties=property_suggestions_to_dict(draft.property_suggestions),
        affective_fields=draft.affective_fields,
        temporal_scope=draft.temporal_scope,
    )


def _enrich_claim(
    draft: CandidateClaimDraft,
    source: SourceRecordRef,
    task: ExtractionTask,
) -> CandidateClaim:
    return CandidateClaim(
        **_base_candidate_payload(draft, source, task),
        claim_type=draft.claim_type,
        text=draft.text,
        about_refs=list(draft.about_refs),
        properties=property_suggestions_to_dict(draft.property_suggestions),
        valid_from=draft.valid_from,
        valid_to=draft.valid_to,
        contradiction_refs=list(draft.contradiction_refs),
    )


def _enrich_perception(
    draft: CandidatePerceptionDraft,
    source: SourceRecordRef,
    task: ExtractionTask,
) -> CandidatePerception:
    return CandidatePerception(
        **_base_candidate_payload(draft, source, task),
        target_ref=draft.target_ref,
        description=draft.description,
        perception_type=draft.perception_type,
        emotional_summary=draft.emotional_summary,
        emotional_valence=draft.emotional_valence,
        emotional_intensity=draft.emotional_intensity,
        emotion_tags=list(draft.emotion_tags),
        original_user_words=draft.original_user_words,
        source_kind=draft.source_kind,
        temporal_scope=draft.temporal_scope,
    )


def _enrich_relationship_context(
    draft: CandidateRelationshipContextDraft,
    source: SourceRecordRef,
    task: ExtractionTask,
) -> CandidateRelationshipContext:
    return CandidateRelationshipContext(
        **_base_candidate_payload(draft, source, task),
        from_ref=draft.from_ref,
        to_ref=draft.to_ref,
        relationship_type=draft.relationship_type,
        relationship_kind=draft.relationship_kind,
        relationship_detail=draft.relationship_detail,
        status=draft.status,
        closeness=draft.closeness,
        description=draft.description,
        emotional_summary=draft.emotional_summary,
        emotional_valence=draft.emotional_valence,
        emotional_intensity=draft.emotional_intensity,
        emotion_tags=list(draft.emotion_tags),
        original_user_words=draft.original_user_words,
        temporal_scope=draft.temporal_scope,
    )


def _enrich_metadata_patch(
    draft: CandidateMetadataPatchDraft,
    source: SourceRecordRef,
    task: ExtractionTask,
) -> CandidateMetadataPatch:
    return CandidateMetadataPatch(
        **_base_candidate_payload(draft, source, task),
        target_ref=draft.target_ref,
        operation=draft.operation,
        path=draft.path,
        value=_coerce_property_value(draft.value_text, draft.value_kind),
        previous_value=(
            _coerce_property_value(draft.previous_value_text, draft.value_kind)
            if draft.previous_value_text is not None
            else None
        ),
        reason=draft.reason,
    )


def _base_candidate_payload(
    draft: CandidateBaseDraft,
    source: SourceRecordRef,
    task: ExtractionTask,
) -> dict[str, Any]:
    return {
        "local_ref": draft.local_ref,
        "evidence_refs": _evidence_refs(draft.evidence, source),
        "source_refs": [source.source_id],
        "ambiguity_flags": list(draft.ambiguity_flags),
        "requires_confirmation": draft.requires_confirmation,
        "metadata": {
            "schema_layer": "backend_enriched",
            "task_id": task.task_id,
            "task_type": str(task.task_type),
        },
    }


def _evidence_refs(
    evidence: Sequence[EvidenceSpanDraft],
    source: SourceRecordRef,
) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for item in evidence:
        if not item.evidence_text and item.span_start is None and item.span_end is None:
            continue
        refs.append(
            EvidenceRef(
                source_id=source.source_id,
                evidence_text=item.evidence_text,
                span_start=item.span_start,
                span_end=item.span_end,
            ),
        )
    return refs


def _coerce_property_value(value: str | None, value_kind: str) -> Any:
    if value is None:
        return None
    text = value.strip()
    if value_kind == "number":
        try:
            number = float(text)
        except ValueError:
            return value
        return int(number) if number.is_integer() else number
    if value_kind == "boolean":
        normalized = text.lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
        return value
    if value_kind == "list":
        return [part.strip() for part in text.split(",") if part.strip()]
    return value
