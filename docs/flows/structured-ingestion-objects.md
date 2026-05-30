# Structured Ingestion Objects

## Purpose

The ingestion pipeline needs well-defined intermediate objects between raw input, LLM extraction, clarification, entity resolution, and graph writes. These objects prevent the LLM from directly mutating memory and make the pipeline auditable, testable, and resumable.

## Required Object Layers

### SourceRecord

The immutable input record.

Core fields:

- `source_id`
- `source_type`
- `channel`
- `external_id`
- `author`
- `created_at`
- `received_at`
- `content_ref`
- `raw_text`
- `derived_from_source_id`
- `metadata`

For voice messages, the original audio and derived transcript should be represented separately. The audio source preserves the raw artifact, while the transcript source gives the extraction pipeline text to process.

### ExtractionRun

The model or tool execution that processed a source.

Core fields:

- `extraction_run_id`
- `source_id`
- `processor`
- `processor_version`
- `model`
- `prompt_version`
- `schema_version`
- `started_at`
- `completed_at`
- `status`

Speech-to-text runs should also be represented as extraction or processing runs, with model/provider information and transcript confidence metadata.

### CandidateEntity

A proposed entity before resolution.

Core fields:

- `candidate_id`
- `entity_type`
- `display_name`
- `description`
- `aliases`
- `typed_properties`
- `affective_fields`
- `metadata`
- `evidence_refs`
- `confidence`
- `missing_fields`
- `ambiguity_flags`

### CandidateRelationship

A proposed relationship between candidate or existing entities.

Core fields:

- `candidate_relationship_id`
- `relationship_type`
- `from_ref`
- `to_ref`
- `properties`
- `affective_fields`
- `metadata`
- `evidence_refs`
- `confidence`
- `temporal_scope`
- `ambiguity_flags`

### CandidateClaim

A proposed factual statement that may not fit cleanly as a direct relationship.

Core fields:

- `candidate_claim_id`
- `claim_type`
- `text`
- `about_refs`
- `properties`
- `metadata`
- `evidence_refs`
- `confidence`
- `valid_from`
- `valid_to`
- `contradiction_refs`

### CandidatePerception

A proposed subjective perception before validation and graph linking. It can target any memory-bearing node or a relationship context.

Core fields:

- `candidate_perception_id`
- `target_ref`
- `description`
- `perception_type`
- `emotional_summary`
- `emotional_valence`
- `emotional_intensity`
- `emotion_tags`
- `original_user_words`
- `source_kind`: user_stated, llm_inferred, system_derived.
- `temporal_scope`
- `evidence_refs`
- `confidence`
- `requires_confirmation`

### CandidateRelationshipContext

A proposed relationship-as-memory object. Use this when a relationship has its own emotional tone, temporal history, evidence, or narrative description.

Core fields:

- `candidate_relationship_context_id`
- `from_ref`
- `to_ref`
- `relationship_type`
- `status`
- `closeness`
- `description`
- `emotional_summary`
- `emotional_valence`
- `emotional_intensity`
- `emotion_tags`
- `original_user_words`
- `temporal_scope`
- `evidence_refs`
- `confidence`
- `requires_confirmation`

### CandidateMetadataPatch

A proposed addition or update to structured fields or metadata.

Core fields:

- `patch_id`
- `target_ref`
- `operation`: add, update, remove, confirm, expire.
- `path`
- `value`
- `previous_value`
- `reason`
- `evidence_refs`
- `confidence`
- `requires_confirmation`

This is useful for contact details, enriched place data, aliases, profile memory updates, and other incremental changes.

### ClarificationRequest

A question that must be answered before a decision is safe or useful.

Core fields:

- `clarification_id`
- `question`
- `reason`
- `target_refs`
- `options`
- `free_text_allowed`
- `blocking`
- `created_at`
- `expires_at`

### ResolutionDecision

The result of matching a candidate to graph state.

Core fields:

- `decision_id`
- `candidate_ref`
- `decision_type`: create, match_existing, merge, reject, keep_pending, ask_clarification.
- `target_entity_id`
- `scores`
- `reasons`
- `requires_confirmation`
- `decided_at`

### GraphWritePlan

The deterministic write plan generated after validation and resolution.

Core fields:

- `write_plan_id`
- `source_id`
- `nodes_to_create`
- `nodes_to_update`
- `relationships_to_create`
- `relationships_to_update`
- `claims_to_create`
- `perceptions_to_create`
- `relationship_contexts_to_create`
- `metadata_patches`
- `evidence_links`
- `idempotency_keys`

## Validation Rules

Before writing to the graph:

- Object schema must be valid.
- Entity and relationship types must be allowed.
- Required fields must be present or explicitly marked unknown.
- Evidence references must point to stored sources.
- Candidate references must resolve to candidate or existing graph IDs.
- Sensitive fields must follow confirmation policy.
- Contact details must be normalized when possible.
- External enrichment must include provider provenance.
- Idempotency keys must be present for source-derived writes.

## Why This Matters

Without structured ingestion objects, the system will be hard to debug. A bad graph write could come from extraction, resolution, clarification, or persistence, but there would be no clean boundary to inspect.

These objects make it possible to:

- Replay ingestion.
- Compare prompt versions.
- Test extraction quality.
- Explain why a merge happened.
- Ask better clarification questions.
- Prevent duplicate writes.
- Roll back or supersede incorrect decisions.

## MVP Scope

The first implementation does not need every field above, but it should establish the object boundaries from the beginning:

- `SourceRecord`
- `ExtractionRun`
- `CandidateEntity`
- `CandidateRelationship`
- `CandidatePerception`
- `CandidateRelationshipContext`
- `ClarificationRequest`
- `ResolutionDecision`
- `GraphWritePlan`

`CandidateClaim`, `CandidateMetadataPatch`, and enrichment-specific objects can become mandatory once the first text ingestion path is stable.
