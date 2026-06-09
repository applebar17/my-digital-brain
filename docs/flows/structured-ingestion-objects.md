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
  flags, and typed property suggestions. They must stay light,
  field-described, generation-friendly, and metadata-poor.
- Backend records are enriched objects. They add generated IDs, `source_id`,
  `source_refs`, `EvidenceRef`, extraction run refs, timestamps, statuses,
  metadata, validation state, and persistence-ready provenance.

The LLM must not output backend-owned fields such as `source_id`,
`mention_scan_id`, `extraction_plan_id`, `task_id`, candidate IDs,
`source_refs`, `EvidenceRef`, raw UUIDs, or backend metadata. Backend code
injects those fields after validating the draft.

Free-form LLM metadata is not allowed in draft schemas. When the model sees an
additional property worth storing, it returns a typed property suggestion:
`key`, `value_text`, `value_kind`, and optional `reason`. Backend code decides
whether that suggestion becomes a typed field, governed metadata, or is ignored.

Draft objects may be deterministically enriched through conversion or
inheritance, but provider structured-output schemas must always use the light
draft class. Enriched backend fields such as IDs, source refs, provenance,
validation state, and persistence metadata must not leak into model-facing
schemas.

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

### GraphContextPack

An ingestion-specific compact context object built before structured reasoning.
It is produced by backend retrieval and compaction, not by the model.

Wave-1 baseline input:

- whole source text or transcript embedded as one query;
- hybrid graph search top-k results;
- hydrated graph targets and nearby relationships.

Core fields:

- `context_pack_id`
- `source_id` for backend ownership, not normally rendered to the LLM
- `retrieval_strategy`: `whole_source_hybrid`, not normally rendered to the LLM
- `retrieved_entities`
- `retrieved_relationships`
- `retrieved_memories`
- `known_aliases`
- `known_relationship_contexts`
- `potential_duplicate_hints`
- `llm_alias_map`
- `compact_summary`

Rules:

- Prefer short LLM-facing aliases such as `NODE_000001`.
- Exclude raw UUID-heavy graph payloads unless a backend step needs them.
- Exclude provider traces, raw metadata blobs, and unrelated neighborhoods.
- Do not require generated natural-language graph queries in wave 1.

If implementation already uses `GraphContextPackage`, that contract can be
reused for this purpose as long as the ingestion-specific v1 strategy and
low-noise fields are preserved.

### GraphContextPackRenderer

`GraphContextPack` is a backend context object. It should not be injected into
LLM payloads wholesale. Dedicated renderer services must produce task-specific
LLM-friendly views.

Renderer examples:

- `render_for_reasoning`
- `render_for_entity_planning`
- `render_for_relationship_planning`
- `render_for_missing_entity_planning`
- `render_for_entity_extraction`
- `render_for_relationship_extraction`

Each renderer chooses the minimum useful fields for the receiving process. Some
calls may need only `compact_summary`; others may need aliases plus duplicate
hints, or only relationship snippets around resolved entities.

Usually exclude from LLM payload views:

- `source_id`
- retrieval strategy
- raw metadata
- internal graph IDs
- trace/debug fields
- unrelated retrieved entities or relationships

Usually include when relevant:

- compact summary
- LLM-facing aliases
- known aliases or nicknames
- relevant entities
- relevant relationships
- duplicate hints
- relationship context snippets

### Reusable LLM Transform Package

Reasoning and planning objects should be produced through reusable LLM-backed
information-transform packages, not one-off ingestion-only prompts.

Baseline transform input:

- general system prompt template;
- dedicated purpose/guidelines;
- dedicated context information;
- usable conversation history when relevant;
- optional prior compact tool outputs;
- current time/timezone when relevant;
- selected model route;
- dedicated structured output model.

Baseline transform output:

- a structured reasoning artifact, or
- a structured planning artifact.

The current reasoning checkpoint implementation already follows this shape. The
planning side should mirror it so ingestion entity plans, ingestion relationship
plans, query retrieval plans, correction plans, maintenance plans, and later
duplicate-review plans can share one backend planning primitive with different
guidelines, context, model route, and output schema.

### PlanningTransformContext

A generic model-facing planning context for the reusable planning primitive.
This is the planning analogue of the reusable reasoning checkpoint context.

Core fields:

- `planning_id`
- `purpose_guidelines`
- `goal`
- `input_context`
- `reasoning_artifact`
- `conversation`
- `current_time`
- `timezone`
- `prior_tool_outputs`
- `expected_output_schema`

Rules:

- `input_context` is caller-shaped and process-specific.
- `reasoning_artifact` is optional but should be provided when planning follows
  a reasoning step.
- The output schema is caller-selected.
- The planner returns ordered process actions only.
- The planner must not extract candidates, validate candidates, resolve
  duplicates, build write plans, or mutate storage.

### StructuredReasoningCheckpoint

A structured model output produced by the reusable reasoning transform before
planning. It interprets the source in the presence of the `GraphContextPack`.

LLM draft fields:

- `summary`
- `entity_notes`
- `alias_notes`
- `relationship_notes`
- `duplicate_notes`
- `node_vs_detail_notes`
- `user_owner_notes`
- `context_gaps`
- `clarification_candidates`

The reasoning checkpoint is not a graph mutation and not a write plan. It
should produce concise free-text notes and interpretations that help later
model steps avoid confusion. Do not over-structure v1 reasoning; detailed
storage behavior belongs in guidelines and backend validation.

Clarification candidates use a doubt-oriented shape:

- `doubt`: what the model is unsure about.
- `reason`: why resolving the doubt may matter.
- `target_refs`: affected local refs or graph aliases.
- `options`: one prose string describing plausible interpretations supported
  by context, not an authoritative option list.
- `blocking`: whether the process must wait before candidate generation.

Example:

```text
Mention "Merc" is likely the user's nickname for Matteo Mercoldi. Treat it as
an alias candidate for Matteo Mercoldi, not as a separate Person.
```

### SemanticIngestionPlanDraft

The older high-freedom model-facing planner output. It remains useful as the
generic planning concept, but the wave-1 ingestion refinement splits planning
into entity and relationship phases so one planner call does not own the whole
memory-writing problem.

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

### EntityIngestionPlanDraft

The model-facing entity-only planning output for the refined baseline. It
should be produced by the reusable planning transform with entity-specific
guidelines, context, and output schema.

Inputs:

- source text or transcript;
- `GraphContextPack`;
- `StructuredReasoningCheckpoint`;
- current time/timezone when relevant.

LLM draft fields:

- `reason`
- `entity_actions`
- `clarification`
- `context_gaps`

Each entity action should stay minimal:

- `action_ref`
- `goal`
- `mention_text`
- `suggested_entity_type`
- `alias_notes`
- `duplicate_hint_refs`
- `details_to_keep_as_context`
- `evidence_text`
- `notes`

Rules:

- Plan entity candidates only.
- Identify aliases and nicknames as aliases, not separate entities.
- Identify low-salience details that should remain event/context metadata.
- Do not produce relationship candidates.
- Do not output backend IDs, graph write operations, or unsupported node fields.

### RelationshipIngestionPlanDraft

The model-facing relationship-only planning output for the refined baseline. It
should be produced by the reusable planning transform with relationship-specific
guidelines, resolved entity context, and output schema.

Inputs:

- source text or transcript;
- relationship-focused reasoning from the reasoning checkpoint;
- resolved entity map;
- compact graph relationship context.

LLM draft fields:

- `reason`
- `actions`
- `missing_entities`
- `clarification`
- `context_gaps`

Each relationship action should stay minimal:

- `action_ref`
- `goal`
- `from_ref`
- `to_ref`
- `relationship_intent`
- `storage_shape`: direct_relationship, relationship_context, perception,
  event_link, place_link, or metadata_note.
- `evidence_text`
- `depends_on`
- `notes`

Rules:

- Plan relationships only after entity resolution has produced a resolved
  entity map.
- Reference only resolved local refs, staged entity refs, or provided graph
  aliases.
- Emit `MissingEntityRequiredDraft` when a necessary endpoint is missing.
- Do not freely create new entities.
- Do not produce graph write operations.

### MissingEntityRequiredDraft

A lightweight relationship-planning output used when a blocked relationship
needs an endpoint that was not produced by the entity plan.

Core fields:

- `missing_ref`
- `reason`
- `mention_text`
- `suggested_entity_type`
- `needed_for_relationship_ref`
- `relationship_goal`
- `source_evidence`
- `required_resolution_hint`
- `blocking`

Process intent:

```text
relationship planning emits MissingEntityRequiredDraft
  -> missing-entity planning receives it as structured guidance
  -> only missing entities are planned and validated
  -> resolved entity map is updated
  -> blocked relationship actions are reprocessed
  -> relationship plans are merged
```

### ExtractionPlan

The generic backend-compiled plan for focused extraction work. In the older
planner-first flow, it was produced from `SemanticIngestionPlanDraft`. In the
wave-1 refined flow, backend compilation may produce separate entity and
relationship extraction plans from `EntityIngestionPlanDraft` and
`RelationshipIngestionPlanDraft`.

Backend record fields:

- `extraction_plan_id`
- `source_id`
- `context_package_id`
- `execution_mode`: entity_preparation, relationship_preparation,
  supplemental_entity_preparation, simple_single_pass, focused_extraction,
  needs_context_expansion, needs_clarification_first.
- `reason`
- `tasks`
- `clarification`
- `context_gaps`
- `created_at`

The deterministic compiler creates tasks from structured plan actions, schedules
entity/ref-producing tasks before ref-consuming tasks, and injects ontology,
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

Alias semantics:

- LLM-facing `aliases` are extraction, retrieval, resolution, and
  context-building hints.
- Aliases do not define node identity.
- Aliases are not automatically writable node properties.
- Backend services decide whether aliases become canonical aliases, search
  aliases, governed metadata, description text, or are ignored.
- If a target node type does not support aliases, validation/write planning
  must not copy draft aliases directly onto that node.

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

In the refined baseline, relationship candidates are produced only after entity
validation has produced a resolved entity map. Relationship drafts must not point
to unknown local refs.

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

A doubt that may need user clarification before a decision is safe or useful.
All clarification handling allows free text; ingestion contracts do not carry a
`free_text_allowed` flag.

Core fields:

- `clarification_id`
- `doubt`
- `reason`
- `target_refs`
- `options`: one prose string describing plausible interpretations, not an
  authoritative option array.
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

### ResolvedEntityMap

The backend handoff object produced after entity candidate validation and
resolution. It is consumed by relationship planning and extraction.

Core fields:

- `resolved_entity_map_id`
- `source_id`
- `candidate_entity_refs`
- `local_ref_to_target`
- `staged_creates`
- `staged_updates`
- `matched_existing`
- `rejected_candidates`
- `pending_duplicate_reviews`
- `validation_errors`

Each map entry should explain whether the local ref points to:

- an existing graph alias;
- a staged create operation;
- a staged update operation;
- a rejected candidate;
- a pending duplicate review.

Relationship planning may only use refs that resolve to existing graph aliases
or staged create/update operations. Pending or rejected refs are not valid
relationship endpoints.

Relationship-planning payloads should receive a rendered view of the map:
usable refs, display labels, entity types, duplicate/ambiguity notes, and only
the minimum staged status needed to plan relationships. Backend-heavy staged
operation payloads should remain outside the LLM view.

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

For the refined wave-1 ingestion baseline:

- Entity candidates are validated before relationship planning.
- Entity creation remains staged until deterministic validation and duplicate
  handling complete.
- Relationship candidates must reference only the resolved entity map or
  provided graph aliases.
- `missing_entity_required` is the only allowed way for relationship planning
  to request a new endpoint.
- Qualitative duplicate judging and user confirmation are reserved for later
  waves.

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
- `GraphContextPack` or an equivalent low-noise `GraphContextPackage`
- `GraphContextPackRenderer`
- `PlanningTransformContext`
- `StructuredReasoningCheckpoint`
- `EntityIngestionPlanDraft`
- `RelationshipIngestionPlanDraft`
- `MissingEntityRequiredDraft`
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
- `ResolvedEntityMap`
- `GraphWritePlan`

`CandidateClaim`, `CandidateMetadataPatch`, and enrichment-specific objects can become mandatory once the first text ingestion path is stable.
