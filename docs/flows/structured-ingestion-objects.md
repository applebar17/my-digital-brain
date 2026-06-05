# Structured Ingestion Objects

## Purpose

The ingestion pipeline needs well-defined intermediate objects between raw input, LLM extraction, clarification, entity resolution, and graph writes. These objects prevent the LLM from directly mutating memory and make the pipeline auditable, testable, and resumable.

## Required Object Layers

### Draft Versus Backend Record Boundary

Objects that are returned by an LLM are not the same objects that downstream
backend services validate and persist.

Use two layers:

- `*Draft` contracts are LLM-facing structured outputs. They contain semantic
  content, local candidate refs, graph aliases, evidence text/spans, ambiguity
  flags, and typed property suggestions.
- Backend records are enriched objects. They add generated IDs, `source_id`,
  `source_refs`, `EvidenceRef`, extraction run refs, timestamps, statuses,
  metadata, and persistence-ready provenance.

The LLM must not output backend-owned fields such as `source_id`,
`mention_scan_id`, `extraction_plan_id`, `task_id`, candidate IDs,
`source_refs`, `EvidenceRef`, raw UUIDs, or backend metadata. Backend code
injects those fields after validating the draft.

Free-form LLM metadata is not allowed in draft schemas. When the model sees an
additional property worth storing, it returns a typed property suggestion:
`key`, `value_text`, `value_kind`, and optional `reason`. Backend code decides
whether that suggestion becomes a typed field, governed metadata, or is ignored.

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

### MentionScan

A cheap shallow pass over source text or transcript. It exists to drive compact graph-context retrieval before the ingestion planner runs.

Backend record fields:

- `mention_scan_id`
- `source_id`
- `mentions`
- `created_at`
- `metadata`

LLM draft fields:

- `mentions`

The mention scan should not create final entities or relationships. It only identifies likely names, places, events, dates, topics, relationship hints, and affective hints.

### Mention

A shallow mention found in the source.

Backend record fields:

- `mention_id`
- `kind`: person, place, event, organization, object, animal, social_circle, topic, date, relationship_context, perception, claim.
- `text`
- `evidence_text`
- `span_start`
- `span_end`
- `possible_normalized_value`
- `ambiguity_hint`

LLM draft fields are the same semantic fields without `mention_id` or metadata.

### SemanticIngestionPlanDraft

The high-freedom model-facing planner output.

LLM draft fields:

- `execution_mode`
- `reason`
- `actions`
- `clarification`
- `context_gaps`

Each semantic action contains:

- `action_ref`
- `action_kind`
- `goal`
- `evidence_text`
- `concept_kinds`
- `concepts`
- `depends_on`
- `context_refs`
- `notes`

The semantic planner may organize the narrative and identify dependencies, but
it must not choose graph labels, relationship types, write-plan operations,
persistence fields, or backend-owned IDs.

### ExtractionPlan

The backend-compiled plan produced from `SemanticIngestionPlanDraft` after
mention scan and compact graph-context retrieval.

Backend record fields:

- `extraction_plan_id`
- `source_id`
- `context_package_id`
- `execution_mode`: simple_single_pass, focused_extraction, needs_context_expansion, needs_clarification_first.
- `reason`
- `tasks`
- `clarification`
- `context_gaps`
- `created_at`

The deterministic compiler creates tasks from semantic actions, schedules
anchor/ref-producing tasks before ref-consuming tasks, and injects ontology,
allowed aliases, candidate refs, previous compact action summaries, and source
refs into backend task metadata.

### ExtractionTask

A focused extraction instruction.

Backend record fields:

- `task_id`
- `task_type`
- `target_ref`
- `evidence_text`
- `source_refs`
- `expected_output`
- `required_context_refs`
- `notes`

Tasks are not LLM planner output. They are backend-compiled focused extraction
instructions. Task types may include person, place, event, claim, perception,
relationship_context, relationship_state, metadata_patch, and link extraction.

### CandidateEntity

A proposed entity before resolution.

Backend record fields:

- `candidate_id`
- `entity_type`
- `display_name`
- `description`
- `aliases`
- `typed_properties`
- `affective_fields`
- `metadata`
- `evidence_refs`
- `missing_fields`
- `ambiguity_flags`

LLM draft fields:

- `local_ref`
- `entity_type`
- `display_name`
- `description`
- `aliases`
- `property_suggestions`
- `affective_fields`
- `evidence`
- `missing_fields`
- `ambiguity_flags`

`entity_type` is enum-constrained to LLM-creatable memory labels only:
`Person`, `Event`, `Place`, `Organization`, `Object`, `Animal`,
`SocialCircle`, and `Topic`. Backend-owned labels such as `Claim`,
`Perception`, `RelationshipContext`, `Source`, `ExtractionRun`,
`ChangeRecord`, `ContradictionRecord`, and `MergeRecord` are not generic entity
choices for the model.

### CandidateRelationship

A proposed relationship between candidate or existing entities.

Backend record fields:

- `candidate_relationship_id`
- `relationship_type`
- `from_ref`
- `to_ref`
- `relationship_kind`
- `relationship_detail`
- `properties`
- `affective_fields`
- `metadata`
- `evidence_refs`
- `temporal_scope`
- `ambiguity_flags`

LLM draft fields use `property_suggestions` and evidence text/spans instead of
backend `properties`, metadata, source refs, or evidence refs.

`relationship_type` is enum-constrained. For v1 social relationships use only:

```text
RELATIONSHIP_WITH
```

and set `relationship_kind` to one of:

```text
friend | family | partner | former_partner | colleague | classmate | acquaintance
```

Preserve source wording in `relationship_detail`, for example `brother`,
`girlfriend`, or `university friend`.

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
- `relationship_kind`
- `relationship_detail`
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

### CandidateMemoryGraph

The assembled candidate graph produced before validation and resolution.

Core fields:

- `candidate_graph_id`
- `source_id`
- `extraction_plan_id`
- `candidate_entities`
- `candidate_relationships`
- `candidate_claims`
- `candidate_perceptions`
- `candidate_relationship_contexts`
- `candidate_metadata_patches`
- `local_ref_map`
- `evidence_refs`
- `ambiguity_flags`
- `missing_fields`

The candidate graph is not a write plan. It is the structured proposal that validation and resolution turn into a `GraphWritePlan` or `ClarificationRequest`.

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

### ContradictionJudgeRequest

A request created when a memory-writing agent has grounded doubt that a proposed write may conflict with existing memory.

Core fields:

- `judge_request_id`
- `proposed_write_ref`
- `retrieved_context_refs`
- `affected_entity_refs`
- `affected_relationship_refs`
- `source_refs`
- `agent_doubt`
- `requested_at`

The `agent_doubt` should be a short explanation, not a final ruling.

### ContradictionJudgeDecision

The structured output from the contradiction judge.

Core fields:

- `judge_decision_id`
- `judge_request_id`
- `decision`: no_conflict, nuance, temporal_update, contradiction, needs_clarification.
- `severity`: low, medium, high.
- `reason`
- `graph_action`: allow_write, write_as_disputed, create_contradiction_record, create_relationship_state, ask_user.
- `clarification_question`
- `inspected_context_refs`
- `decided_at`

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
- `contradiction_records_to_create`
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
- Contradiction judge requests must include the proposed write, retrieved context, and agent doubt.
- Contradiction judge decisions must be structured and must not mutate graph state directly.
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
- `MentionScan`
- `Mention`
- `ExtractionPlan`
- `ExtractionTask`
- `CandidateEntity`
- `CandidateRelationship`
- `CandidatePerception`
- `CandidateRelationshipContext`
- `CandidateMemoryGraph`
- `ContradictionJudgeRequest`
- `ContradictionJudgeDecision`
- `ClarificationRequest`
- `ResolutionDecision`
- `GraphWritePlan`

`CandidateClaim`, `CandidateMetadataPatch`, and enrichment-specific objects can become mandatory once the first text ingestion path is stable.
