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
        "nodes, do not resolve duplicates, and preserve short evidence text."
    )
    planner_system_prompt = (
        "Create a backend-executable extraction plan after reading source text, shallow "
        "mentions, and compact graph context. Choose the cheapest safe execution mode. "
        "Return focused tasks only; do not create graph writes. Use only aliases present "
        "in context, candidate refs you define later, or source refs. Ask clarification "
        "first when ambiguity blocks useful extraction."
    )
    extractor_system_prompt = (
        "Execute only the focused extraction task. Return structured candidates of the "
        "requested type only. Preserve evidence, original user words, affective meaning, "
        "missing fields, and ambiguity flags. Use provided aliases and local refs instead "
        "of raw internal graph ids. Do not guess when information is missing."
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
            "mention_scan": mention_scan.model_dump(mode="json", exclude_none=True),
            "compact_graph_context": context.model_dump(mode="json", exclude_none=True),
        }

    def extraction_input(
        self,
        source: SourceRecordRef,
        task: ExtractionTask,
        context: IngestionContextPackage,
    ) -> dict[str, Any]:
        return {
            "source": self.source_payload(source),
            "task": task.model_dump(mode="json", exclude_none=True),
            "compact_graph_context": context.model_dump(mode="json", exclude_none=True),
        }

    def source_payload(self, source: SourceRecordRef) -> dict[str, Any]:
        payload = source.model_dump(mode="json", exclude_none=True)
        payload.pop("metadata", None)
        return payload
