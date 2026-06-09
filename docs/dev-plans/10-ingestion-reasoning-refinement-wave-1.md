# Ingestion Reasoning Refinement Wave 1

## Summary

Refine memory ingestion from the current planner-first shape into a
reasoning-first, entity-first, relationship-second pipeline.

The purpose of this wave is to reduce duplicated entities, invalid candidate
fields, missing relationships, and relationship candidates that point to
ambiguous or uncreated nodes.

Locked baseline:

- Source context is retrieved before reasoning.
- Reasoning, planning, candidate preparation, validation, and write execution
  are separate activities.
- Reasoning and planning are reusable LLM-backed information-transform
  primitives, not ingestion-only one-off components.
- Entity work happens before relationship work.
- Entity creation is staged until duplicate handling and deterministic
  validation have run.
- Relationship planning receives the resolved entity map and must not invent
  unresolved endpoints.
- Production ingestion completes only after validated write-plan execution and
  durable graph writes.
- Tool/state completion returns one compact tool output to the invoking
  conversation state, which then continues the normal message/tool-output loop.
- Provider tool loops preserve assistant `tool_calls`, matching `tool`
  messages, and final assistant messages as state-local message deltas for
  tracing, replay, and downstream context construction.
- V1 keeps validation simple and deterministic. Qualitative duplicate judging,
  richer merge decisions, and user confirmation workflows are reserved for a
  later wave.

## Target Flow

```text
source
  -> whole-source hybrid graph retrieval
  -> compact Graph Context Pack
  -> structured reasoning checkpoint

  -> entity plan
  -> entity candidates
  -> duplicate judge / entity validation
  -> resolved entity map + staged entity create/update ops

  -> relationship plan using resolved entity map
  -> relationship candidates
  -> relationship validation
  -> write
```

Relationship planning may discover a required endpoint that the entity track
missed:

```text
relationship plan
  -> missing_entity_required?
      -> supplemental entity candidate
      -> duplicate judge / entity validation
      -> update resolved entity map
  -> relationship candidates
```

## Reusable Reasoning And Planning Pillar

Reasoning and planning are logical process steps that can be re-engaged at
different points of ingestion, correction, maintenance, duplicate review,
querying, and future graph operations. They must therefore be implemented as
simple reusable packages for transforming information, not as hardcoded
ingestion-only agents.

Baseline package shape for every reusable reasoning or planning call:

```text
general system prompt template
  + dedicated purpose/guidelines
  + dedicated context information
  + usable history when relevant
  + optional prior compact tool outputs
  + selected model route
  + dedicated structured output model
  -> structured reasoning or planning artifact
```

Current implementation check:

- `reasoning_checkpoint` already follows this baseline:
  - general prompt template: `reasoning_checkpoint/v1.system.md`;
  - purpose-specific `ReasoningPurposeGuidelines`;
  - caller-provided `input_context`;
  - optional `ConversationContext`;
  - optional compact `GraphContextPackage`;
  - optional prior `ToolResultContext` outputs;
  - `AgenticReasoningService.reason(..., output_schema=...)` supports the
    default result schema or a caller-provided Pydantic output schema.
- Planning does not yet fully follow this baseline. Current ingestion and query
  planning are separate purpose-specific implementations. Wave 1 must introduce
  or align a generalized planning primitive that mirrors the reasoning package.

Planning baseline:

- The base planning prompt explains planning responsibilities and boundaries.
- Purpose-specific guidelines explain the concrete process being planned.
- Caller context contains the relevant process state and constraints.
- Conversation/history is included when it affects the plan.
- The caller selects the output schema, such as `EntityIngestionPlanDraft`,
  `RelationshipIngestionPlanDraft`, `QueryRetrievalPlan`, or a later duplicate
  review plan.
- The caller selects or allows routing for the model task.
- The planner produces ordered process actions only. It does not extract
  candidates, validate candidates, resolve duplicates, build write plans, or
  mutate storage.

## Contract And Schema Baseline

This refinement starts with documentation and contract/schema modeling only.
Runtime flow changes, prompt wiring, agent routing, extraction orchestration,
and write behavior are deferred until the contract slice is implemented and
tested.

Execution order:

1. Lock the documentation baseline for the contract/schema wave.
2. Add lightweight contracts, exports, and schema tests.
3. Add context-rendering services for LLM payloads.
4. Later wire flows, agents, prompts, extraction, validation, and write
   orchestration onto the new contracts.

Final runtime decision:

- `IngestionService` is the reasoning-first runtime service.
- The old planner-first production path is removed instead of bridged.
- `CANDIDATE_READY` is an internal diagnostic/UAT checkpoint only.
- Production chat success requires `WRITTEN`.
- `WRITE_PLAN_READY` is not a user-facing success when the user asked to store a
  memory; it is a diagnostic failure unless the caller is explicitly running a
  dry-run/UAT path.
- Clarification answers are normal new user messages; backend pending state
  stores compact resumable context and does not concatenate answers into source
  text.

Draft/enriched object rule:

- LLM-facing `*Draft` objects are light, field-described,
  generation-friendly, and metadata-poor.
- Backend-enriched records add deterministic IDs, source refs, provenance,
  metadata, validation status, timestamps, and persistence fields.
- Provider structured-output schemas must use the light draft classes, not
  enriched backend records.
- Enrichment may use inheritance or conversion, but backend-owned fields must
  not leak into model-facing schemas.

Context rendering rule:

- `GraphContextPack` may contain structured backend context.
- LLM payloads must receive rendered views from dedicated context-rendering
  services.
- Renderers select the task-relevant subset, such as compact summary, aliases,
  relationships, duplicate hints, or relationship-context snippets.
- Most LLM calls do not need `source_id`, retrieval strategy, raw metadata,
  internal IDs, or trace/debug fields.

Alias rule:

- Aliases are extraction, retrieval, resolution, and context-building hints.
- Aliases do not define node identity.
- Aliases are not automatically writable node properties.
- Backend services decide whether aliases become canonical aliases, search
  aliases, governed metadata, description text, or are ignored.

## Locked Principles

1. **Graph context v1 stays simple.**

   Do not generate multiple natural-language graph queries in wave 1. Embed the
   whole source text and retrieve the top-k graph items through hybrid search.

2. **The Graph Context Pack is compact and renderer-ready.**

   It should contain useful nearby graph state, not raw graph dumps. It should
   summarize relevant existing entities, aliases, known relationships, nearby
   memories or events, and potential duplicate hints. LLM calls receive
   task-specific rendered views of this pack, not the raw pack by default.

3. **Reasoning comes before planning.**

   The first model-backed ingestion step is a structured reasoning checkpoint,
   not an extraction planner.

4. **Reasoning clarifies future doubts.**

   The reasoning output must help later steps understand aliases, entity
   identity, user-specific relationships, salience, ambiguous wording, and
   storage implications.

5. **Reasoning is structured interpretation, not graph mutation.**

   It does not write memory, decide database IDs, emit graph write operations,
   or bypass validation.

6. **Planning is a reusable structured transform.**

   Entity and relationship planning must use the generalized planning package
   with dedicated guidelines, dedicated context, history when relevant, model
   routing, and dedicated output models.

7. **Planning and extraction are split by target type.**

   Entity planning/extraction and relationship planning/extraction are separate
   model tasks with separate contracts.

8. **Entity work happens first.**

   Relationships are planned only after the entity track has produced a
   resolved entity map or staged entity operations.

9. **Entity creation is staged.**

   Candidate entities are not durable nodes until duplicate handling and
   deterministic validation complete.

10. **Duplicate handling is a required process slot.**

   Before injecting new candidates, the system must compare them against the
   retrieved graph context and current graph state.

11. **V1 duplicate handling is conservative.**

   Wave 1 reserves the duplicate-judge slot, but only deterministic validation
   is required initially. Qualitative duplicate judging and user confirmation
   are later work.

12. **Duplicate merge behavior is a target capability.**

   When a candidate is judged to be a duplicate in a later wave, useful
   information should transfer to the existing node: aliases, relationships,
   additional metadata, log or activity references, and refreshed embeddings.

13. **Relationship planning uses resolved references only.**

   The relationship planner receives the resolved entity map and should produce
   relationships only between known local refs or existing graph aliases.

14. **Missing endpoints are explicit.**

   If a relationship requires an entity that was not created or resolved, the
   relationship step emits `missing_entity_required` instead of inventing an
   endpoint silently.

15. **V1 validation is deterministic.**

   Validation should check schema compatibility, required fields, forbidden
   fields, allowed ontology values, resolved endpoints, and exact duplicate
   edges. It should not attempt qualitative semantic judging yet.

16. **No full qualitative traceability requirement in v1.**

   Evidence and source grounding remain useful, but wave 1 does not require a
   complete qualitative trace-back system or LLM judge for every write.

17. **The process should reduce hallucination through context shaping.**

   Each step receives only the context required for its responsibility:
   reasoning receives the source and compact graph context; entity planning
   receives reasoning focused on entities; relationship planning receives the
   resolved entity map and relationship reasoning.

## Step Responsibilities

### 1. Whole-Source Hybrid Graph Retrieval

Kind: backend process.

Input:

- normalized source text or transcript
- current time and timezone
- owner/session scope and privacy/lifecycle filters

Behavior:

- embed the whole source text
- run hybrid graph retrieval with top-k limits
- hydrate relevant graph records
- compact entities and relationships into model-facing aliases

Output:

- `GraphContextPack`

Out of scope:

- query fan-out
- generated natural-language search queries
- qualitative duplicate judgment

### 2. Graph Context Pack

Kind: backend-built context object.

It should include:

- short graph aliases, not raw UUID-heavy payloads
- existing relevant entities
- aliases and nicknames
- known relationships and relationship contexts
- nearby events or memories when useful
- potential duplicate hints from exact, alias, fuzzy, or hybrid retrieval
- compact source/evidence summaries when already available

It should exclude:

- raw technical metadata
- full graph JSON
- provider traces
- unrelated neighborhoods
- backend-only IDs when aliases are enough

### 3. Structured Reasoning Checkpoint

Kind: model-backed structured reasoning step.

Purpose:

- interpret the source in the presence of graph context
- make ambiguity explicit for later steps
- decide whether mentions are entities, aliases, relationship hints, or
  contextual details
- identify likely user-related storage implications

Required output themes:

- summary
- entity notes
- alias notes
- relationship notes
- duplicate notes
- node-versus-detail notes
- user/owner notes
- context gaps
- clarification candidates when needed
- next context summary

Example expected reasoning:

```text
New entity candidate: Matteo Mercoldi.
The user also calls him "Merc".
"Merc" should be treated as an alias/nickname of Matteo Mercoldi, not as a
separate Person node.
```

The checkpoint must not output hidden chain-of-thought. It should output
concise notes and interpretations that later planning or extraction steps can
consume. Keep the structure light; detailed storage policy belongs in
guidelines and backend validation, not in a heavy reasoning object.

### 4. Entity Plan

Kind: model-backed structured plan.

Input:

- source text
- Graph Context Pack
- structured reasoning checkpoint

Output:

- entity-only ingestion plan

Allowed:

- identify which entities must be prepared
- identify which mentions should become aliases
- identify which details should remain metadata or event description
- request clarification only when entity ambiguity blocks useful storage

Forbidden:

- relationship candidates
- graph write operations
- backend IDs
- unsupported node fields

### 5. Entity Candidates

Kind: focused structured extraction.

Input:

- entity plan
- source text
- entity-focused reasoning
- graph aliases and duplicate hints

Output:

- schema-compatible entity candidates

Candidate entities must use scoped local refs. They must not use backend-owned
IDs or arbitrary metadata dicts.

### 6. Duplicate Judge / Entity Validation

Kind: backend process in v1; future hybrid process later.

Wave 1 deterministic checks:

- schema fields are allowed for the candidate type
- required fields are present or explicitly unknown
- aliases are accepted only on node types that support aliases
- local refs are unique
- obvious exact duplicate aliases/names are detected
- candidate entity type is allowed

Future target outcomes:

```text
confirmed duplicate -> update existing node
suspected duplicate -> ask user confirmation
not duplicate -> create new node
```

Future duplicate application behavior:

- transfer aliases
- transfer useful relationships
- transfer metadata or activity references
- refresh embeddings for the canonical node

### 7. Resolved Entity Map

Kind: backend-built handoff object.

Purpose:

- give later steps stable references for relationship planning
- prevent relationship candidates from pointing to unresolved endpoints

It maps:

```text
local entity ref -> existing graph alias or staged create/update op
```

### 8. Relationship Plan

Kind: model-backed structured plan.

Input:

- source text
- relationship-focused reasoning
- resolved entity map
- compact graph relationships from the context pack

Output:

- relationship-only ingestion plan with simple ordered actions

Allowed:

- plan relationships between resolved/staged entities
- describe the minimum processing needed for each relationship action
- choose a coarse storage shape such as direct relationship,
  relationship context, perception, event link, place link, or metadata note
- emit `missing_entity_required` when an endpoint is missing

Forbidden:

- free creation of new entities
- relationships to unknown refs
- unsupported edge types
- graph write operations

Minimal relationship action fields:

- `action_ref`
- `goal`
- `from_ref`
- `to_ref`
- `relationship_intent`
- `storage_shape`
- `evidence_text`
- `depends_on`
- `notes`

Missing-entity loop:

```text
plan entities
  -> validate entities
  -> resolve entity map
  -> plan relationships
  -> missing_entity_required
  -> re-plan only the missing entity from MissingEntityRequiredDraft
  -> validate only new entities
  -> update resolved entity map
  -> process blocked relationship actions
  -> merge relationship plans
```

`MissingEntityRequiredDraft` must carry enough structured guidance to plan the
missing entity and resume the blocked relationship action after the entity map
is updated.

### 9. Relationship Candidates

Kind: focused structured extraction.

Output:

- schema-compatible relationship candidates
- relationship contexts, perceptions, event participation links, or place links
  when those are the correct storage shapes

Relationship candidates must reference only:

- resolved entity local refs
- existing graph aliases provided in context
- staged entity refs from the resolved entity map

### 10. Relationship Validation

Kind: backend process.

Wave 1 deterministic checks:

- endpoints resolve
- relationship type is allowed
- relationship kind/detail fit the allowed ontology
- exact duplicate edge is not created
- forbidden fields are absent
- required temporal or descriptive fields are present when the storage shape
  requires them

### 11. Write

Kind: backend process.

Only validated operations become persistent graph writes.

The write step owns:

- generated IDs
- source refs
- timestamps
- evidence refs
- lifecycle state
- graph persistence
- vector refresh triggers when implemented

## Wave 4 Scope: Relationship Candidates And UAT Traces

Wave 4 should make the reasoning-first ingestion path inspectable and relationship-ready
without relying on graph/database integrations for UAT. The slice should focus
on relationship candidate preparation, missing-entity detection, and local text
reports that expose the process under the hood.

Runtime boundary:

- The old graph/database write behavior remains outside this wave.
- The UAT scripts may call configured model providers through the project
  environment, but they must not require graph or database access.
- The scripts render local, committable `.txt` reports for human review.
- Reports are diagnostic artifacts, not production telemetry or API contracts.

Relationship-candidate scope:

- compile `RelationshipIngestionPlanDraft` actions into relationship extraction
  requests;
- enforce resolved endpoint usage through `ResolvedEntityMap`;
- emit and consume `MissingEntityRequiredDraft` when a relationship endpoint is
  missing;
- re-plan only the missing entity from the missing-entity guidance;
- update the resolved entity map with the supplemental entity result;
- resume blocked relationship planning/extraction after the entity map is
  complete;
- produce final entity and relationship candidate summaries;
- keep local UAT trace scripts graph/database-free even though production
  ingestion now continues through write execution when graph services are
  configured.

### UAT Script 1: Local Conversation Entry Trace

Add a local script for a provided text file acting as the user's message.
Suggested path:

```text
scripts/render_uat_refined_ingestion_trace.py
```

Inputs:

- `--input`: local `.txt` source file;
- `--output`: local `.txt` report path;
- optional provider/model/env overrides following existing project
  configuration patterns;
- optional empty or fixture-based graph-context placeholder.

The script should process the text as a conversation entry and render:

1. user request/source text;
2. routing decision and selected ingestion path;
3. graph context placeholder or empty rendered pack;
4. reasoning system prompt, model input, and model output;
5. entity-planning system prompt, model input, and model output;
6. entity extraction or candidate-preparation input and output;
7. resolved entity map;
8. relationship-planning system prompt, model input, and model output;
9. relationship extraction or candidate-preparation input and output;
10. final candidate graph summary.

Acceptance criteria:

- running the script does not require backend API, graph database, vector
  database, or persisted memory state;
- the report is readable without raw UUID-heavy metadata by default;
- prompt/input/output blocks are visible enough to debug model behavior;
- the script clearly marks provider-generated content as non-deterministic.

### UAT Script 2: Missing-Entity Relationship Trace

Add a second local script for a controlled missing-entity scenario. Suggested
path:

```text
scripts/render_uat_missing_entity_trace.py
```

Inputs:

- `--input`: fictitious ingestion request text;
- `--entities`: fixture file containing predefined entity candidates or a
  prebuilt resolved entity map;
- `--output`: local `.txt` report path;
- optional provider/model/env overrides following existing project
  configuration patterns.

The fixture must intentionally omit one relationship endpoint so the
relationship planner has to decide whether a `MissingEntityRequiredDraft` is
needed before relationship candidates are prepared.

The report should render:

1. fictitious user request/source text;
2. predefined entity candidates or initial resolved entity map;
3. relationship-planning system prompt, model input, and model output;
4. detected `MissingEntityRequiredDraft` values;
5. missing-entity planning system prompt, model input, and model output;
6. supplemental entity extraction or candidate-preparation output;
7. updated resolved entity map;
8. resumed relationship plan or relationship extraction output;
9. final entity and relationship candidate summary.

Acceptance criteria:

- the missing endpoint is visible in the report before supplemental entity
  planning starts;
- relationship candidates are not produced against unresolved refs;
- the final report shows whether the planner detected the missing entity before
  preparing the relationship;
- the script remains graph/database-free.

## Prompt And Contract Requirements

Prompting should be detailed but not overloaded. Each prompt must describe only
the current step's responsibility.

Prompt layering:

```text
base reasoning or planning template
  + step-specific guidelines
  + step-specific context
  + selected structured output schema
```

Do not duplicate whole prompts for every use case when the reusable base
template plus dedicated guidelines can express the step.

Required examples:

- nickname/alias handling:

  ```text
  "Merc" -> alias of Matteo Mercoldi, not a separate Person.
  ```

- family relationship:

  ```text
  "mio fratello Lorenzo" -> Person Lorenzo plus owner-to-Lorenzo family
  relationship with relationship_detail="brother".
  ```

- ambiguous social group:

  ```text
  "il suo gruppo" -> SocialCircle candidate only if the group is meaningful;
  do not emit unsupported fields such as aliases when the target schema does
  not allow them.
  ```

- low-salience detail:

  ```text
  "uova con zucchine e peperoni" -> event detail unless the object is durable,
  recurring, or semantically important.
  ```

The prompts should include explicit rules for:

- entity versus detail
- alias versus new entity
- relationship versus metadata
- user/owner as relationship endpoint
- SocialCircle field restrictions
- unresolved endpoint handling
- no graph mutation from model output

## V1 Scope

Wave 1 should implement or align:

- reusable planning primitive mirroring the existing reusable reasoning
  checkpoint package
- lightweight LLM-facing draft contracts and backend-enriched handoff records
- compact `GraphContextPack`
- context-rendering service interfaces for LLM-friendly payloads
- lightweight ingestion-specific reasoning output
- entity-only planning draft
- relationship-only planning draft
- staged entity resolution map contract
- deterministic validation contract boundaries
- `MissingEntityRequiredDraft`

The first implementation slice under this wave is contract/schema-only. It
must not alter runtime flow, prompt execution, agent routing, extraction
orchestration, or write behavior.

## Explicitly Out Of Scope For Wave 1

- generated natural-language graph query fan-out
- qualitative LLM duplicate judge
- user confirmation UI for suspected duplicates
- full merge/split application logic
- broad prompt optimization framework beyond the base reusable
  reasoning/planning template pattern
- source-level qualitative trace-back for every decision
- ontology expansion beyond the currently allowed node and relationship types
- replacing the graph/vector retrieval architecture

## Implementation Order

1. Lock documentation for the contract/schema baseline.
2. Confirm the existing reusable reasoning checkpoint is the baseline pattern:
   general template, purpose guidelines, dedicated context, history when
   relevant, model routing, and caller-selected output schema.
3. Add a reusable planning primitive contract that mirrors the reasoning
   package:
   general planning template, purpose guidelines, dedicated context, history
   when relevant, model routing, and caller-selected output schema.
4. Add or update structured contracts for `GraphContextPack`,
   `StructuredReasoningCheckpoint`, `PlanningTransformContext`, entity plan,
   relationship plan, `ResolvedEntityMap`, and `MissingEntityRequiredDraft`.
5. Add context-rendering service interfaces for process-specific LLM payload
   views.
6. Add exports and schema tests only.
7. Promote the reasoning-first runtime under the `IngestionService` name.
8. Remove old planner-first production wiring and deprecated runtime assertions.
9. Wire relationship planning, missing-entity handling, candidate graph
   validation, deterministic resolution, write-plan generation, write-plan
   validation, durable graph writes, and post-write vector refresh.
10. Keep UAT trace scripts diagnostic: they may expose internal checkpoints, but
    production model-facing history receives compact tool outputs only.
11. Audit remaining state/tool paths for proper contextual handoff semantics.

## UAT Signals

Wave 1 should improve the following visible behaviors:

- aliases such as `Merc` do not become duplicate people when a canonical person
  is available
- family wording such as `mio fratello` creates or retrieves the brother node
  and owner relationship context
- relationships are not dropped because endpoints were created later
- relationship candidates do not point to unknown refs
- SocialCircle candidates do not contain unsupported fields such as `aliases`
- low-salience objects are less likely to become standalone nodes
- graph search for relationship-heavy queries has relevant connected nodes and
  edges to render
- local UAT trace reports expose routing, prompts, inputs, outputs, entity
  candidates, relationship candidates, and missing-entity handling without
  requiring graph/database integrations

## Future Follow-Ups

- Explore generated natural-language graph query fan-out after whole-source
  retrieval is stable.
- Design the qualitative duplicate judge.
- Design user confirmation for suspected duplicates and proposed merges.
- Implement non-destructive duplicate merge application.
- Re-embed canonical nodes after duplicate updates and relationship transfers.
- Add evaluation examples for alias handling, kinship, social circles,
  cohabitants, event participants, and low-salience objects.
