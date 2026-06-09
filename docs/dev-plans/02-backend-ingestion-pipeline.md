# Backend Ingestion Pipeline Definition

## Goal

Define the transport-neutral backend services that turn stored text or transcript sources into validated memory graph changes.

This plan does not define the Telegram bot or the user-facing chat loop. The chat layer will call these ingestion services through a small, strict tool surface. The ingestion package owns graph-context retrieval, structured reasoning, entity and relationship planning, candidate preparation, validation, resolution, clarification proposals, and graph write plans.

The next ingestion quality baseline is defined in
[Ingestion reasoning refinement wave 1](10-ingestion-reasoning-refinement-wave-1.md).

## Locked Architecture Decisions

- Ingestion is a backend service layer, not a Telegram-specific flow.
- `ai/` remains provider infrastructure only. It supplies LLM, embedding, model routing, and speech-to-text capabilities through protocols.
- The ingestion package contains application business logic: memory extraction contracts, graph-context packaging, structured reasoning, planning, candidate assembly, validation, resolution, and write-plan execution.
- The conversational LLM chooses actions and proposes parameters. Backend services validate parameters and perform all state changes.
- The LLM never writes directly to the graph, relational store, source files, or vector store.
- LLM structured outputs use `*Draft` contracts. Backend code enriches those
  drafts into canonical records by adding generated IDs, source provenance,
  evidence refs, timestamps, status fields, and backend metadata.
- LLM-facing schemas must not require or accept raw backend IDs, `source_id`,
  generated candidate IDs, `source_refs`, `EvidenceRef`, raw UUIDs, or free-form
  backend metadata. The only model-facing identifiers are scoped local refs and
  provided graph aliases.
- LLM-facing arbitrary fields are represented as typed property suggestions.
  Backend code decides whether suggestions become typed graph properties,
  governed metadata, or are ignored.
- Top-level conversational action space is intentionally small:
  - default answer path: no tool
  - `start_memory_ingestion`
  - `query_memory_context`
  - `propose_memory_correction`
- Resume, cancel, expire, clarification handling, write-plan validation, and write execution are process states or backend service operations. They are not broad top-level LLM tools.
- Pending ingestion state is context for resumption, not a rigid chat workflow. The chat/runtime layer decides whether a later message resumes the pending process.
- Complexity is not classified from raw user text alone. For the wave-1
  refinement baseline, the source is first embedded as a whole, retrieved
  through hybrid graph search, compacted into a Graph Context Pack, and then
  interpreted by a structured reasoning checkpoint.
- Graph writes are always deterministic backend operations applied from a validated `GraphWritePlan`.
- Voice messages are first transcribed into text through the AI provider layer. The transcript then enters the same ingestion path as typed text while preserving evidence links to the original audio.

## Required Layers

### Conversational Orchestrator

Owned by the future chat layer.

Responsibilities:

- Decide whether to answer normally or invoke a top-level action.
- Pass strict parameters to ingestion/query/correction tools.
- Display clarification questions and summaries to the user.
- Keep conversational behavior dynamic without owning graph mutations.
- Attach pending process context and conversation history when invoking subprocesses.

The orchestrator is not an ingestion extractor and must not produce graph writes.

### Ingestion Process Orchestrator

Owned by the ingestion package.

Responsibilities:

- Create or resume ingestion sessions.
- Store source references received from the caller.
- Run source storage, whole-source hybrid graph-context retrieval, structured
  reasoning, entity planning, entity candidate preparation, entity
  validation/resolution, relationship planning, relationship candidate
  preparation, relationship validation, and write-plan execution.
- Return either an ingestion result, a clarification request, or a failure state.
- Persist only the minimal process state needed for resumption and auditability.

### Internal Ingestion Services

These are backend services, not general-purpose LLM tools:

- graph context pack builder and renderer
- `StructuredReasoningService`
- reusable `PlanningService`
- entity planning guidelines and plan compiler
- relationship planning guidelines and plan compiler
- entity candidate preparers
- relationship candidate preparers
- `CandidateMemoryGraphAssembler`
- `IngestionValidator`
- `ResolutionService`
- `GraphWritePlanExecutor`

## Refined Reasoning Flow

The system must not run extraction blindly from raw source text. It should first
collect graph context, reason over the source and context, then split entity and
relationship work.

Required target flow:

1. Store source text or transcript.
2. Embed the whole source text.
3. Retrieve top-k relevant graph items through hybrid search.
4. Hydrate and compact retrieved graph state into a `GraphContextPack`.
5. Run a structured reasoning checkpoint.
6. Run an entity-only ingestion planner through the reusable planning
   primitive.
7. Prepare entity candidates.
8. Validate entity candidate schemas and deterministic constraints.
9. Resolve obvious existing entity matches and stage entity create/update ops.
10. Produce a `ResolvedEntityMap`.
11. Run relationship-only planning from the resolved entity map through the
    reusable planning primitive.
12. Prepare relationship, relationship-context, perception, event-link, or
    metadata-link candidates.
13. If a required endpoint is missing, emit `missing_entity_required` and loop
    through supplemental entity handling.
14. Validate relationship schemas, allowed ontology values, and endpoints.
15. Produce a deterministic `GraphWritePlan` or `ClarificationRequest`.
16. Execute the validated write plan through graph services.

Generated natural-language graph query fan-out is out of scope for this
baseline. The source-as-a-whole hybrid search is the first context strategy.

The backend may override or reject any model-produced plan if it is invalid,
too large, unsafe, unsupported, or inconsistent with deterministic validation.

## Example Flows

The following examples describe the current reasoning-first implementation
shape.

### Entity And Relationship Flow

User source:

```text
Yesterday I had dinner with Alessandro at Pizzeria Napoli.
```

Compact graph context:

```json
{
  "people": [
    {"alias": "NODE_001", "name": "Alessandro Verdi", "summary": "close friend"}
  ],
  "places": [
    {"alias": "NODE_002", "name": "Pizzeria Napoli", "city": "Milan"}
  ]
}
```

Reasoning checkpoint:

```json
{
  "summary": "The source describes a dinner involving Alessandro and Pizzeria Napoli.",
  "entity_notes": ["Alessandro is a person candidate.", "Pizzeria Napoli is a place candidate."],
  "relationship_notes": ["The dinner happened at Pizzeria Napoli and involved Alessandro."]
}
```

Entity plan:

```json
{
  "actions": [
    {
      "action_ref": "ENTITY_ACTION_001",
      "goal": "Extract Alessandro as a person candidate.",
      "mention_text": "Alessandro",
      "suggested_entity_type": "Person",
      "evidence_text": "Yesterday I had dinner with Alessandro at Pizzeria Napoli"
    },
    {
      "action_ref": "ENTITY_ACTION_002",
      "goal": "Extract Pizzeria Napoli as a place candidate.",
      "mention_text": "Pizzeria Napoli",
      "suggested_entity_type": "Place",
      "evidence_text": "at Pizzeria Napoli"
    }
  ]
}
```

Relationship plan after entity resolution:

```json
{
  "actions": [
    {
      "action_ref": "RELATIONSHIP_ACTION_001",
      "goal": "Connect the dinner, participant, and place using the source narrative.",
      "from_ref": "CANDIDATE_EVENT_001",
      "to_ref": "CANDIDATE_PLACE_001",
      "relationship_type": "HAPPENED_AT"
    }
  ]
}
```

### Clarification During Planning Or Resolution

User source:

```text
Yesterday I met Marco in Milan.
```

Compact graph context:

```json
{
  "people": [
    {"alias": "NODE_001", "name": "Marco Rossi", "summary": "university friend"},
    {"alias": "NODE_002", "name": "Marco Bianchi", "summary": "former coworker"},
    {"alias": "NODE_003", "name": "Marco", "summary": "gym acquaintance"}
  ],
  "places": [
    {"alias": "NODE_004", "name": "Milan", "type": "city", "country": "Italy"}
  ]
}
```

Clarification result:

```json
{
  "clarification": {
    "doubt": "The name Marco may refer to multiple known people.",
    "reason": "There are several plausible Marco nodes in the graph context.",
    "options": "Could be Marco from university, Marco the former coworker, or Marco from the gym.",
    "blocking": true
  }
}
```

No graph write plan is produced until clarification resolves the blocking ambiguity.

### Focused Extraction

User source:

```text
I saw Alessandro again. We used to be very close as teenagers, but now I feel distant from him. I still care about him, but his personality always felt oppressive to me.
```

Planner result after context retrieval:

```json
{
  "execution_mode": "focused_extraction",
  "reason": "The source contains relational history, current relationship state, and affective perception.",
  "tasks": [
    {"task_type": "person_reference", "target_ref": "NODE_001"},
    {"task_type": "relationship_context", "target_ref": "RELCTX_001"},
    {"task_type": "relationship_state", "target_ref": "RELCTX_001"},
    {"task_type": "perception", "target_ref": "NODE_001"}
  ]
}
```

The backend runs only the focused extractors needed for those tasks.

## Wave 0: Baseline Decisions

- Use Python for backend unless a strong reason appears otherwise.
- Use Pydantic objects for structured extraction and graph write plans.
- Keep the AI Manager dynamic and agentic.
- Keep graph writes validated through graph services.
- Store raw sources before model processing.
- Treat voice transcripts as derived source artifacts linked to original audio.
- Use the provider abstractions from [AI provider foundation](07-ai-provider-foundation.md).
- Support OpenAI and/or Azure OpenAI behind the provider abstraction rather than coupling ingestion logic to one vendor.

## Wave 1: Contracts And Deterministic Skeleton

Status: implemented in `src/my_digital_brain/ingestion/` with unit coverage in `tests/test_ingestion_contracts.py`.

### Summary

Create the ingestion package, structured contracts, deterministic validation, local-reference assembly, and orchestration boundaries. This wave does not require real LLM calls and does not need to write to Neo4j yet.

The purpose is to make the ingestion pipeline testable before prompts are introduced.

### Key Changes

- Add `src/my_digital_brain/ingestion/`.
- Add `ingestion/enums.py`:
  - `SourceType`
  - `SourceChannel`
  - `ExtractionExecutionMode`
  - `ExtractionTaskType`
  - `CandidateRefKind`
  - `ClarificationStatus`
  - `ResolutionDecisionType`
  - `GraphWritePlanStatus`
  - `IngestionStatus`
- Add `ingestion/contracts.py`:
  - `SourceRecordRef`
  - `ExtractionRunRef`
  - `ExtractionPlan`
  - `ExtractionTask`
  - `EvidenceRef`
  - `TemporalScope`
  - `AffectiveFields`
  - `CandidateEntity`
  - `CandidateRelationship`
  - `CandidateClaim`
  - `CandidatePerception`
  - `CandidateRelationshipContext`
  - `CandidateMetadataPatch`
  - `CandidateMemoryGraph`
  - `ClarificationRequest`
  - `ResolutionDecision`
  - `GraphNodeWrite`
  - `GraphRelationshipWrite`
  - `GraphWritePlan`
  - `IngestionResult`
- Add `ingestion/protocols.py` for internal service contracts:
  - `FocusedExtractor`
  - `CandidateMemoryGraphAssembler`
  - `IngestionValidator`
  - `ResolutionService`
  - `GraphWritePlanBuilder`
  - `GraphWritePlanExecutor`
  - `GraphVectorizationService`
  - `IngestionProcessStore`
- Add `ingestion/assembly.py`:
  - assemble extractor outputs into a `CandidateMemoryGraph`
  - validate local candidate references
  - keep a local reference map such as `CANDIDATE_PERSON_001`
- Add `ingestion/validation.py`:
  - validate allowed graph labels against graph registries
  - validate allowed relationship types against graph registries
  - reject unknown local references
  - reject candidate writes without source/evidence references when required
  - verify clarification requests have a question and reason
  - verify write plans contain only validated refs
- Add `ingestion/service.py`:
  - orchestration skeleton that accepts injected protocol implementations
  - returns `IngestionResult`
  - supports fake/no-op services for tests

### Contract Requirements

All LLM-facing draft contracts must have concise field descriptions because Pydantic field descriptions are part of the prompt surface.

Every backend-enriched candidate object that can affect graph state must include:

- source references
- evidence text or evidence refs
- original user words when relevant
- missing fields
- ambiguity flags
- local refs or graph aliases only, never arbitrary raw graph IDs in LLM-facing fields

The corresponding LLM-facing candidate drafts include evidence text/spans and
property suggestions only. Backend enrichment injects `source_refs`,
`EvidenceRef`, candidate IDs, and backend metadata before validation.

The `GraphWritePlan` must be backend-generated. It is not a direct LLM output schema.

### Out Of Scope

- Real LLM mention scanning.
- Real LLM extraction.
- Graph context retrieval.
- Entity resolution beyond stub decisions.
- Neo4j write execution.
- Telegram/chat integration.
- Contradiction judge invocation.

### Tests

- Contract validation for minimal and rich payloads.
- Enum values match the docs and graph registries.
- Candidate reference validation rejects unknown local refs.
- Candidate entity labels and relationship types reject unknown values.
- Candidate graph assembly preserves source/evidence refs.
- Ingestion service can run with fake dependencies.
- Invalid plans return structured validation errors.

### Completion Criteria

- A developer can import `my_digital_brain.ingestion` and construct a valid `CandidateMemoryGraph`.
- A fake ingestion run can pass through service orchestration without touching providers or Neo4j.
- Validation can reject bad labels, relationship types, local refs, and missing evidence.

## Wave 2: Context-Aware AI Planning And Focused Extraction

Status: superseded by the reasoning-first runtime and covered by
`tests/test_ingestion_extractors.py`, `tests/test_ingestion_runtime.py`, and
`tests/test_ingestion_write_execution.py`.

### Summary

Add AI-backed reasoning, planning, and focused candidate extraction services.
The current runtime proceeds through durable graph write when write execution is
enabled.

### Key Changes

- Add whole-source graph context pack building and renderer-facing views.
- Add structured reasoning and reusable planning checkpoint services.
- Produce `IngestionReasoningCheckpointDraft`, `EntityIngestionPlanDraft`,
  `RelationshipIngestionPlanDraft`, and `MissingEntityRequiredDraft`.
- Add deterministic focused plan builders for entity, supplemental entity, and
  relationship extraction.
- Build candidate/ref catalogs, resolved entity-map refs, compact previous-step
  summaries, and ontology constraints into low-freedom extractor calls.
- Add `ingestion/extractors/`.
  - `entity.py`
  - `relationship.py`
  - `claim.py`
  - `perception.py`
  - `relationship_context.py`
  - `metadata_patch.py`
- Add `ingestion/prompts.py` or `ingestion/prompt_builders.py`.
  - Keeps prompt text close to structured contracts.
  - Builds low-noise context for each extractor.
  - Keeps focused tasks small.
- Add model routing integration for reasoning, planning, and extraction model
  selection.

### Prompt And Schema Rules

- Reasoning and planning prompts must receive graph/process context through the
  backend-rendered system prompt, while source/user text remains conversation
  message content.
- Planning prompts must use only aliases and refs supplied in context.
- Focused extractors must only extract the requested task.
- Extractors must preserve evidence text and original user wording.
- Extractors should use `unknown`, `missing_fields`, or `ambiguity_flags` instead of guessing.
- Extractors return `Candidate*DraftBatch` schemas to the model; backend
  enrichment returns canonical `Candidate*` records to downstream services.
- Tool/provider errors must be verbose enough for orchestration to retry, ask clarification, or fail cleanly.

### Out Of Scope

- Real graph mutation.
- Rich duplicate resolution.
- Contradiction judge flow.
- Chat pending-process integration.
- Batch reprocessing.
- Evaluation set automation.

### Tests

- Reasoning and planning services return lightweight structured drafts.
- Planner rejects unknown aliases and unsupported task types.
- Graph context pack renderer returns low-noise views with aliases.
- Focused extractors produce only their target candidate types.
- Focused extractors preserve evidence and original user words.
- Service orchestration runs the reasoning-first focused extraction flow.
- No test uses a real OpenAI/Azure call.

### Completion Criteria

- A stored text source can produce a mention scan, context-aware extraction plan, and candidate graph using fake or stubbed providers.
- Planner and extractor outputs validate against contracts.
- The code path remains transport-neutral and does not depend on Telegram.

## Wave 3: Resolution, Write Plans, And Execution

Status: implemented with conservative resolution, deterministic write-plan building, graph-service execution, in-memory source/session snapshots for local/private runs, and coverage in `tests/test_ingestion_write_execution.py`.

### Summary

Turn validated candidate graphs into deterministic graph write plans, resolve obvious existing matches, create clarification requests for ambiguity, and execute safe plans through graph services.

This wave makes the first useful ingestion path possible.

### Key Changes

- Add `ingestion/resolution.py`.
  - Exact name matching.
  - Alias matching.
  - Existing graph alias resolution.
  - Obvious source-backed matches.
  - Ambiguous matches produce `ClarificationRequest`.
  - No aggressive merge logic in MVP.
- Add `ingestion/write_plan.py`.
  - Converts validated candidates plus resolution decisions into `GraphWritePlan`.
  - Uses deterministic idempotency keys.
  - Preserves source and extraction run references.
  - Maps candidate-local refs to graph IDs or planned node IDs.
- Add `ingestion/executor.py`.
  - Executes `GraphWritePlan` through graph service/repository APIs.
  - Creates nodes, relationships, claims, perceptions, relationship contexts, and evidence links.
  - Does not accept raw LLM output.
  - Produces an auditable `IngestionResult`.
- Add basic source/session integration.
  - Store source refs before processing when a process store is injected.
  - Record ingestion result snapshots, candidate graph snapshots, write-plan snapshots, and pending clarification context.
  - Expire pending process snapshots through explicit timestamps.
  - Use `InMemoryIngestionProcessStore` for local/private runs; relational persistence can map the same snapshots to existing operational tables.
- Preserve provider request context at the service boundary.
- AI-backed services pass source id, purpose, schema id, route metadata, and source/channel metadata into provider requests.
- Durable provider request-log persistence remains owned by the AI/operational logging layer.
- Provider request context may carry backend IDs for tracing, but those IDs are
  not part of model-facing prompt payloads or structured response schemas.

### Resolution Policy

Wave 3 resolution is conservative.

Allowed automatic decisions:

- Create new node when no plausible existing match exists.
- Match existing node when an exact alias/name match is unambiguous.
- Link to existing context when the planner used a provided alias.

Clarification is required when:

- one mention maps to multiple plausible people/places/events
- a relationship endpoint is unresolved
- a risky merge would be needed
- a required source/evidence link is missing

Merges, split/revert flows, and rich duplicate reasoning remain later work.

### Write Execution Policy

The executor must:

- validate write plan status before execution
- resolve all local refs before mutation
- reject unknown graph labels or relationship types
- use graph services instead of raw arbitrary Cypher
- preserve source and extraction run provenance
- create idempotency keys for source-derived writes
- return structured success, partial, or failure results

### Out Of Scope

- Contradiction judge implementation.
- Advanced merge application from ingestion.
- Embedding/vector writes unless already needed for obvious resolution.
- Telegram bot state handling.
- User-facing answer generation.
- Frontend review UI.

### Tests

- Exact/alias resolution matches one existing node.
- Ambiguous resolution returns clarification.
- Write plan builder maps candidate refs to planned graph writes.
- Write plan builder rejects unresolved refs.
- Executor calls graph service methods with validated payloads.
- Executor preserves evidence/source refs.
- Reprocessing the same source does not create duplicate planned writes.
- End-to-end fake ingestion path returns written, clarification, and validation-failed results.

### Completion Criteria

- Text memories can create graph nodes and relationships through a validated write plan.
- A voice transcript can enter the same ingestion path as text.
- Ambiguous references can pause ingestion with a structured clarification request.
- Every persisted fact has source or extraction provenance.
- Reprocessing the same source is idempotent at the write-plan level.

## Later Waves

- Agentic contradiction judge invocation.
- Rich entity resolution with embeddings and graph-neighborhood comparison.
- Batch reprocessing when prompts or schemas improve.
- Provider/model routing by difficulty, privacy level, latency budget, and cost budget.
- Extraction evaluation set using personal synthetic examples.
- Multi-source ingestion from documents, images, links, and calendar exports.
- Automatic enrichment requests for places or contacts when useful.
- Background maintenance scans for duplicates, stale facts, and weak metadata.

## Guardrails

- The LLM never writes directly to the graph.
- The LLM chooses actions and proposes parameters; backend services validate and execute.
- Graph write plans must validate before persistence.
- Sensitive facts require privacy-aware handling.
- Pending ingestion sessions expire.
- Pending ingestion sessions do not force the next chat message into a deterministic clarification route.
- Tool-call loops have limits.
- Every persisted fact has source provenance.
- Provider calls are logged with model, prompt/schema version, latency, cost estimate where available, and privacy level.

## Initial Success Criteria

- Text memories can create nodes and relationships.
- Voice memories can be transcribed and ingested through the same text path.
- OpenAI or Azure OpenAI can be swapped through configuration without changing ingestion logic.
- Chroma or Azure AI services can be swapped through the vector store protocol without changing ingestion logic.
- Ambiguous person/place references can trigger a clarification.
- Graph writes are auditable.
- Reprocessing a source does not create duplicate graph pollution.
