from __future__ import annotations

from typing import Any

from my_digital_brain.ingestion.contracts import (
    ExtractionTask,
    IngestionContextPackage,
    MentionScan,
    SourceRecordRef,
)

INGESTION_MENTION_SCAN_TASK = "ingestion_mention_scan"
INGESTION_PLANNING_TASK = "ingestion_planning"
INGESTION_ENTITY_EXTRACTION_TASK = "ingestion_entity_extraction"
INGESTION_RELATIONSHIP_EXTRACTION_TASK = "ingestion_relationship_extraction"
INGESTION_CLAIM_EXTRACTION_TASK = "ingestion_claim_extraction"
INGESTION_PERCEPTION_EXTRACTION_TASK = "ingestion_perception_extraction"
INGESTION_RELATIONSHIP_CONTEXT_EXTRACTION_TASK = "ingestion_relationship_context_extraction"
INGESTION_METADATA_PATCH_EXTRACTION_TASK = "ingestion_metadata_patch_extraction"


class IngestionPromptBuilder:
    """Build compact, low-noise inputs for structured ingestion model calls."""

    mention_scan_system_prompt = (
        "Scan the source for shallow memory mentions only. Return mentions for people, "
        "places, events, organizations, objects, animals, social circles, topics, dates, "
        "relationship contexts, perceptions, claims, and metadata. Do not create graph "
        "nodes, do not resolve duplicates, and preserve short evidence text. When the "
        "source contains emotional or relationship wording, then include perception or "
        "relationship-context mentions. When a mention is ambiguous, then preserve the "
        "ambiguity hint instead of resolving it."
    )
    planner_system_prompt = (
        "Create a backend-executable extraction plan after reading source text, shallow "
        "mentions, and compact graph context. Choose the cheapest safe execution mode. "
        "Return focused tasks only; do not create graph writes. Use only aliases present "
        "in context or candidate refs you define later. Ask clarification "
        "first when ambiguity blocks useful extraction. When one clear factual memory is "
        "present, then choose simple_single_pass. When affective, temporal, or relationship "
        "history is present, then choose focused_extraction. When context is insufficient, "
        "then request context expansion."
    )
    extractor_system_prompt = (
        "Execute only the focused extraction task. Return structured candidates of the "
        "requested type only. Preserve evidence, original user words, affective meaning, "
        "missing fields, and ambiguity flags. Use provided aliases and local refs for "
        "references. Represent extra fields as typed property_suggestions. Do not guess "
        "when information is missing. When the source states emotion or perception, then "
        "preserve the user's wording. When a required field is absent, then mark it missing "
        "rather than inventing it."
    )

    def mention_scan_input(self, source: SourceRecordRef) -> dict[str, Any]:
        return {"source": self.source_payload(source)}

    def planner_input(
        self,
        source: SourceRecordRef,
        mention_scan: MentionScan,
        context: IngestionContextPackage,
    ) -> dict[str, Any]:
        return {
            "source": self.source_payload(source),
            "mention_scan": self.mention_scan_payload(mention_scan),
            "compact_graph_context": self.context_payload(context),
        }

    def extraction_input(
        self,
        source: SourceRecordRef,
        task: ExtractionTask,
        context: IngestionContextPackage,
    ) -> dict[str, Any]:
        return {
            "source": self.source_payload(source),
            "task": self.task_payload(task),
            "compact_graph_context": self.context_payload(context),
        }

    def source_payload(self, source: SourceRecordRef) -> dict[str, Any]:
        payload = source.model_dump(mode="json", exclude_none=True)
        payload.pop("source_id", None)
        payload.pop("external_id", None)
        payload.pop("content_ref", None)
        payload.pop("derived_from_source_id", None)
        payload.pop("metadata", None)
        return payload

    def mention_scan_payload(self, mention_scan: MentionScan) -> dict[str, Any]:
        return {
            "mentions": [
                {
                    key: value
                    for key, value in {
                        "kind": str(mention.kind),
                        "text": mention.text,
                        "evidence_text": mention.evidence_text,
                        "span_start": mention.span_start,
                        "span_end": mention.span_end,
                        "possible_normalized_value": mention.possible_normalized_value,
                        "ambiguity_hint": mention.ambiguity_hint,
                    }.items()
                    if value is not None
                }
                for mention in mention_scan.mentions
            ],
        }

    def task_payload(self, task: ExtractionTask) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "task_type": str(task.task_type),
                "target_ref": task.target_ref,
                "evidence_text": task.evidence_text,
                "expected_output": task.expected_output,
                "required_context_refs": list(task.required_context_refs),
                "notes": task.notes,
            }.items()
            if value not in (None, [], {})
        }

    def context_payload(self, context: IngestionContextPackage) -> dict[str, Any]:
        return {
            "aliases": {alias: alias for alias in context.aliases},
            "entities": list(context.entities),
            "relationships": list(context.relationships),
            "notes": list(context.notes),
        }
