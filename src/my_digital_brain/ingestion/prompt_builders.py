from __future__ import annotations

from typing import Any

from my_digital_brain.ingestion.contracts import (
    ExtractionTask,
    IngestionContextPackage,
    MentionScan,
    SourceRecordRef,
)
from my_digital_brain.ingestion.ontology import ontology_prompt_payload

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
        "Create a semantic ingestion plan after reading source text, shallow mentions, "
        "conversation context, and compact graph context. Organize the user's narrative "
        "into ordered semantic actions with goals, evidence, dependencies, ambiguity "
        "notes, and context gaps. Do not choose graph labels, edge types, write-plan "
        "operations, persistence fields, or backend identifiers. Ask clarification first "
        "when ambiguity blocks useful extraction. When context is insufficient, request "
        "context expansion. When one clear factual memory is present, choose "
        "simple_single_pass with one or more semantic actions. When the source has "
        "affective, temporal, relational, or multi-entity content, choose "
        "focused_extraction with ordered actions."
    )
    extractor_system_prompt = (
        "Execute only the focused extraction task. Return structured candidates of the "
        "requested type only. This is a low-freedom backend-facing step: use only enum "
        "values allowed by the schema and only refs or aliases supplied in the task/context. "
        "Preserve evidence, original user words, affective meaning, missing fields, "
        "ambiguity flags, and source-grounded subtype details. Represent extra fields as "
        "typed property_suggestions. Do not guess when information is missing. For social "
        "relationships, use RELATIONSHIP_WITH plus relationship_kind and preserve wording "
        "such as brother or girlfriend in relationship_detail."
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
            "semantic_planning_policy": {
                "output": "ordered semantic actions, not graph schema decisions",
                "allowed_action_kinds": [
                    "extract_anchors",
                    "extract_event",
                    "connect_entities",
                    "capture_relationship_context",
                    "capture_perception",
                    "capture_claim",
                    "update_metadata",
                ],
            },
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
            "ontology": ontology_prompt_payload(),
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
                "metadata": self._task_metadata_payload(task.metadata),
            }.items()
            if value not in (None, [], {})
        }

    def context_payload(self, context: IngestionContextPackage) -> dict[str, Any]:
        metadata = self._context_metadata_payload(context.metadata)
        return {
            key: value
            for key, value in {
                "aliases": {alias: alias for alias in context.aliases},
                "entities": list(context.entities),
                "relationships": list(context.relationships),
                "notes": list(context.notes),
                "metadata": metadata,
            }.items()
            if value not in ({}, [], None)
        }

    def _task_metadata_payload(self, metadata: dict[str, Any]) -> dict[str, Any]:
        allowed_keys = {
            "semantic_action_ref",
            "semantic_action_kind",
            "semantic_action_goal",
            "semantic_action_index",
            "semantic_depends_on",
            "semantic_concepts",
            "ref_policy",
            "suggested_candidate_refs",
            "candidate_ref_catalog",
            "previous_action_summaries",
            "allowed_graph_aliases",
            "relationship_action_ref",
            "relationship_action_goal",
            "relationship_action_index",
            "relationship_intent",
            "storage_shape",
            "original_from_ref",
            "original_to_ref",
            "resolved_from_ref",
            "resolved_to_ref",
            "relationship_depends_on",
            "ontology",
        }
        return {
            key: value
            for key, value in metadata.items()
            if key in allowed_keys and value not in (None, [], {})
        }

    def _context_metadata_payload(self, metadata: dict[str, Any]) -> dict[str, Any]:
        allowed_keys = {
            "candidate_ref_catalog",
            "previous_action_summaries",
            "current_action",
            "ingestion_ontology",
        }
        return {
            key: value
            for key, value in metadata.items()
            if key in allowed_keys and value not in (None, [], {})
        }
