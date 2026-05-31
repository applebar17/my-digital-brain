# Backend Ingestion Pipeline Definition

## Goal

Define the transport-neutral backend services that turn stored text or transcript sources into validated memory graph changes.

This plan does not define the Telegram bot or the user-facing chat loop. The chat layer will call these ingestion services through a small, strict tool surface. The ingestion package owns memory extraction, context-aware planning, validation, resolution, clarification proposals, and graph write plans.

## Locked Architecture Decisions

- Ingestion is a backend service layer, not a Telegram-specific flow.
- `ai/` remains provider infrastructure only. It supplies LLM, embedding, model routing, and speech-to-text capabilities through protocols.
- The ingestion package contains application business logic: memory extraction contracts, planning, candidate assembly, validation, resolution, and write-plan execution.
- The conversational LLM chooses actions and proposes parameters. Backend services validate parameters and perform all state changes.
- The LLM never writes directly to the graph, relational store, source files, or vector store.
- Top-level conversational action space is intentionally small:
  - default answer path: no tool
  - `start_memory_ingestion`
  - `query_memory_context`
  - `propose_memory_correction`
- Resume, cancel, expire, clarification handling, write-plan validation, and write execution are process states or backend service operations. They are not broad top-level LLM tools.
- Complexity is not classified from raw user text alone. Complexity is decided after a cheap mention scan and compact graph-context retrieval.
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

The orchestrator is not an ingestion extractor and must not produce graph writes.

### Ingestion Process Orchestrator

Owned by the ingestion package.

Responsibilities:

- Create or resume ingestion sessions.
- Store source references received from the caller.
- Run mention scan, context retrieval, planning, extraction, assembly, validation, resolution, and write-plan execution.
- Return either an ingestion result, a clarification request, or a failure state.
- Persist only the minimal process state needed for resumption and auditability.

### Internal Ingestion Services

These are backend services, not general-purpose LLM tools:

- `MentionScanner`
- `IngestionContextRetriever`
- `IngestionPlanner`
- focused extractors
- `CandidateMemoryGraphAssembler`
- `IngestionValidator`
- `ResolutionService`
- `GraphWritePlanExecutor`

## Context-Aware Complexity Flow

The system must not run an expensive rich extraction blindly for every source. It should first collect enough context to choose the correct extraction path.

Required flow:

1. Store source text or transcript.
2. Run a cheap mention scan over the source.
3. Retrieve compact graph context for mentioned people, places, events, organizations, topics, relationship contexts, and likely duplicates.
4. Run an ingestion planner with source text plus compact graph context.
5. The planner returns an `ExtractionPlan` with execution mode and focused tasks.
6. Backend selects the flow from the plan.
7. Focused extractors run only for required tasks.
8. Backend assembles candidates into a `CandidateMemoryGraph`.
9. Validation and resolution produce either a `ClarificationRequest` or a deterministic `GraphWritePlan`.
10. Backend executes the validated write plan through graph services.

The planner should decide among these execution modes:

- `simple_single_pass`: low ambiguity, small memory, few entities, no rich affective or relationship-history content.
- `focused_extraction`: source contains multiple targets, affective content, relationship history, temporal nuance, or richer metadata.
- `needs_context_expansion`: initial graph context is insufficient for a safe plan.
- `needs_clarification_first`: ambiguity blocks useful extraction or safe resolution.

The backend may override or reject an execution mode if the plan is invalid, too large, unsafe, or unsupported.

## Example Flows

### Simple Single Pass

User source:

```text
Yesterday I had dinner with Alessandro at Pizzeria Napoli.
```

Mention scan:

```json
{
  "mentions": [
    {"kind": "person", "text": "Alessandro"},
    {"kind": "place", "text": "Pizzeria Napoli"},
    {"kind": "event", "text": "dinner yesterday"}
  ]
}
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

Planner result:

```json
{
  "execution_mode": "simple_single_pass",
  "tasks": [
    {"task_type": "event", "evidence_text": "Yesterday I had dinner..."},
    {"task_type": "relationship_link", "target_ref": "NODE_001"},
    {"task_type": "place_link", "target_ref": "NODE_002"}
  ],
  "clarification": null
}
```

### Clarification First

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

Planner result:

```json
{
  "execution_mode": "needs_clarification_first",
  "reason": "The person mention 'Marco' maps to three plausible existing people.",
  "tasks": [
    {"task_type": "event", "evidence_text": "Yesterday I met Marco in Milan"}
  ],
  "clarification": {
    "question": "Which Marco do you mean?",
    "options": ["Marco from university", "Marco the former coworker", "Marco from the gym"],
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

## Wave 1: Transport-Neutral MVP Ingestion Core

Implement the core backend service path:

1. Receive a stored text source or transcript source.
2. Run cheap mention scan.
3. Retrieve compact graph context for mentions.
4. Build an `ExtractionPlan`.
5. Run the selected extraction path.
6. Assemble a `CandidateMemoryGraph`.
7. Run deterministic validation.
8. Resolve obvious matches.
9. Produce a `ClarificationRequest` when useful or blocking.
10. Produce and execute a validated `GraphWritePlan` when safe.
11. Return concise ingestion result.

Required structured objects:

- `SourceRecord`
- `ExtractionRun`
- `MentionScan`
- `Mention`
- `ExtractionPlan`
- `ExtractionTask`
- `CandidateEntity`
- `CandidateRelationship`
- `CandidateClaim`
- `CandidatePerception`
- `CandidateRelationshipContext`
- `CandidateMetadataPatch`
- `CandidateMemoryGraph`
- `ClarificationRequest`
- `ResolutionDecision`
- `GraphWritePlan`

Required provider abstractions:

- `LLMProvider`
- `StructuredLLMProvider`
- `SpeechToTextProvider`
- `EmbeddingProvider`
- `VectorStore`
- `ModelRouter`
- `ProviderRequestLog`

Provider abstractions should hide OpenAI versus Azure OpenAI differences from the ingestion pipeline. The vector store abstraction should support Chroma locally and Azure AI services in cloud mode.

## Wave 2: Resolution And Contradiction Handling

- Add richer entity resolution using aliases, embeddings, source context, temporal context, and existing graph neighborhoods.
- Detect likely duplicate people, places, events, and organizations.
- Detect contradictions during ingestion through agentic suspicion over retrieved context, not brittle deterministic rules.
- Ask clarification when contradictions matter.
- Expire or dispute older facts when a new fact clearly supersedes them.
- Preserve both facts when ambiguity remains.

## Wave 3: Advanced Ingestion

- Batch reprocessing of sources when prompts or schemas improve.
- Provider/model routing by task difficulty, privacy level, latency budget, and cost budget.
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
