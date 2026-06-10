# Node Log Vectorization And Update Flow

## Summary

Define the next retrieval and update architecture for short node-level memory
logs, multi-scope vector storage, node summary refresh, and agentic graph update
flows.

This plan extends the graph-RAG baseline. Neo4j remains the source of truth for
memory records, relationships, provenance, lifecycle, and audit history. Vector
stores remain retrieval indexes that point back to authoritative graph records.

The key refinement is to stop treating every retrieval unit as a full node
summary. Short user-stated updates should become first-class semantic log
records linked to a target node, with compact embeddings optimized for precise
retrieval. Node summaries and node-summary embeddings are then refreshed from
recent relevant logs when needed.

## Current Baseline

Current ingestion stores memory in these forms:

- entity nodes, such as `Person`, `Place`, `Event`, `SocialCircle`;
- memory-bearing context nodes, such as `Perception`, `RelationshipContext`,
  `RelationshipState`, `Claim`, and `ProfileMemory`;
- typed graph relationships between nodes;
- metadata patches on existing nodes;
- backend `ChangeRecord` nodes for change/audit history.

Important limitation:

- There is no first-class semantic node activity log today.
- `ChangeRecord` is backend change history. It should not be used as the user
  memory log surface.
- Metadata patches can append values to node properties, but that is not a
  retrieval-friendly or maintainable log model.
- Current vectorization uses the `memory_documents` collection with typed
  embedding documents built from graph records.
- Embedding dimension is currently available at request/provider level, but
  there is no first-class per-scope vector configuration yet.

## Design Principles

- Store short updates as graph memory records, not as hidden metadata.
- Keep vector records small, typed, and hydratable back to graph targets.
- Do not embed raw graph payloads, UUIDs, backend traces, prompts, provider
  logs, or audit metadata.
- Do not create a raw edge-only embedding collection. Raw edges are usually too
  semantically thin.
- Embed relationship meaning through memory-bearing records such as
  `RelationshipContext`, `RelationshipState`, and future relationship logs.
- Use one query embedding per distinct model/dimension scope at query time.
- Merge retrieval results across scopes only after normalizing scores and
  hydrating graph targets.
- Node summaries are maintained views over accumulated memory, not the only
  place where memory lives.

## Vector DB Structure

The target vector structure should move from one generic collection toward
configured retrieval scopes.

### `memory_node_summaries`

Purpose:

- retrieve canonical graph nodes by their compact semantic summary.

Embeds:

- stable entity summaries;
- important aliases where supported;
- compact relationship/profile context;
- durable user-relevant facts.

Primary target:

- the canonical graph node.

Related targets:

- important nearby `RelationshipContext`, `Perception`, `Event`, `Claim`, or
  `Source` records when useful.

Dimension strategy:

- medium or larger dimensions are acceptable because this collection is lower
  cardinality and more semantically broad.

### `memory_micro_logs`

Purpose:

- retrieve precise short user-stated updates and route them back to the target
  node.

Embeds:

- short node activity logs;
- corrections;
- short facts;
- observations;
- status updates;
- preferences or profile updates when represented as node-targeted logs.

Primary target:

- the log record itself, if logs are modeled as graph nodes.

Canonical target:

- the node the log updates or describes.

Related targets:

- source, involved entities, event/place context, and relationship context when
  available.

Dimension strategy:

- smaller dimensions are preferred because texts are short and cardinality will
  be high.

### `memory_contexts`

Purpose:

- retrieve memory-bearing context records that are richer than raw edges but
  more specific than node summaries.

Embeds:

- `Perception`;
- `RelationshipContext`;
- `RelationshipState`;
- `Claim`;
- optionally `Event` or `ProfileMemory` if we choose to split them from node
  summaries.

Primary target:

- the context record.

Related targets:

- perceived target, relationship endpoints, source records, event/place
  context, and other supporting nodes.

Dimension strategy:

- medium dimensions by default. These texts are usually richer than micro logs
  but narrower than whole-node summaries.

### Query Across Multiple Scopes

If scopes use different dimensions or models, the retrieval layer must produce
one query embedding per distinct `(provider, model, dimensions)` tuple.

Example:

```text
query
  -> embed for node-summary scope
  -> search memory_node_summaries
  -> embed for micro-log scope
  -> search memory_micro_logs
  -> embed for context scope
  -> search memory_contexts
  -> normalize and merge hits
  -> hydrate graph targets
  -> expand neighborhoods
  -> rank/render graph context
```

The retrieval response must expose enough diagnostics to explain which scope
produced each hit.

## Node Log Model

Add a first-class semantic log record for user-relevant node updates.

Working label:

- `NodeActivityLog`

Alternative names to consider before implementation:

- `MemoryLog`
- `NodeUpdateLog`
- `ObservationLog`

Baseline fields:

- `id`
- `target_node_id`
- `target_node_label`
- `log_text`
- `log_kind`
- `source_kind`
- `source_ids`
- `extraction_run_ids`
- `original_user_words`
- `temporal_scope`
- `confidence`
- `importance`
- `created_at`
- `updated_at`
- `lifecycle_state`
- `metadata`

Suggested relationship:

```text
(target)-[:HAS_ACTIVITY_LOG]->(log:NodeActivityLog)
```

The log text must be short, human-readable, and semantically meaningful. It
should not be a raw source chunk, JSON payload, prompt trace, or provider log.

## Node Update Flow

### Existing Node Update

```text
source message
  -> graph retrieval for candidate target nodes
  -> reasoning checkpoint
  -> update plan
  -> target resolution
  -> deterministic validation
  -> write node activity log
  -> apply explicit field patches only when safe
  -> vectorize micro log
  -> refresh node summary if trigger fires
  -> refresh node-summary embedding if summary changed
  -> return compact tool output
```

The default action for new user-stated facts about an existing node should be a
log record, not an immediate destructive overwrite of node fields.

Field patches should be reserved for:

- stable identity fields;
- lifecycle/status fields;
- explicit corrections;
- high-confidence deterministic updates;
- backend-owned summary fields after refresh.

### New Node Creation

```text
source message
  -> reasoning checkpoint
  -> entity plan/candidates
  -> duplicate resolution
  -> create node
  -> optionally create initial activity log
  -> create node-summary vector
  -> create micro-log vector if an initial log exists
```

The initial log is useful when the first user statement has retrieval value that
should stay separate from the generated node summary.

### Relationship Or Perception Update

For relationship and perception memories, prefer memory-bearing context records
over raw edge embeddings.

```text
source message
  -> resolve relationship endpoints or perception target
  -> create/update RelationshipContext, RelationshipState, or Perception
  -> vectorize context record
  -> refresh involved node summaries if the context is important
  -> refresh involved node-summary embeddings if summaries changed
```

Raw relationship edges remain graph topology. They should be embedded only when
they have a meaningful textual record attached.

## Node Summary Refresh

Node summaries are compact derived views over durable memory records.

Summary refresh should consider:

- recent `NodeActivityLog` records;
- important `Perception` records;
- relevant `RelationshipContext` and `RelationshipState` records;
- durable `Claim`, `Event`, and `ProfileMemory` records;
- explicit corrections;
- lifecycle and merge/canonical identity.

Refresh triggers:

- a high-importance log is written;
- a configured number of new logs accumulates;
- a relationship/perception context changes;
- a profile memory changes;
- a user explicitly asks to correct or summarize a node;
- a scheduled maintenance job detects stale summaries.

Refresh output:

- compact node `memory_summary` or `context_summary`;
- optional `relationship_summary`;
- optional `recurring_context`;
- summary provenance and refresh timestamp;
- rebuilt `memory_node_summaries` vector entry when the summary checksum changes.

Summary refresh can be deterministic for simple joins at first. LLM-assisted
summarization can be added behind a dedicated process with strict source
grounding and deterministic validation.

## Agentic Node Update Process

The agentic flow should treat graph updates as tool-driven work with
deterministic guardrails.

Baseline process:

```text
conversation state
  -> model detects memory update intent
  -> model calls graph update tool
  -> update tool runs an internal state/process
  -> process searches graph context
  -> process reasons about target and update kind
  -> process asks clarification if target/update is ambiguous
  -> process builds NodeUpdatePlan
  -> deterministic backend validates plan
  -> backend writes graph changes
  -> backend refreshes vectors/summaries as configured
  -> tool returns compact structured output
  -> conversation state appends tool output and continues
```

The model may manage the conversation flow and choose tools, but it must not
directly write graph records. Mutation remains behind backend tools,
validators, write plans, and idempotency.

The tool output should include:

- status;
- target node label/title;
- activity logs created;
- fields patched;
- summaries refreshed;
- vector scopes refreshed;
- clarification needed, if any;
- concise diagnostics for the next model call.

User-facing responses should stay simple and non-technical. Internal tool
outputs may include technical detail when the next state needs it.

## Contracts To Add

Planned lightweight contracts:

- `NodeActivityLogDraft`
- `NodeActivityLog`
- `NodeUpdatePlanDraft`
- `NodeFieldPatchDraft`
- `NodeSummaryRefreshRequest`
- `NodeSummaryRefreshResult`
- `VectorScopeConfig`
- `VectorScopeSearchRequest`
- `VectorScopeSearchResult`
- `MultiScopeRetrievalResult`

Keep LLM-facing drafts small and field-described. Backend-enriched records add
IDs, provenance, lifecycle, validation status, and persistence metadata.

## Implementation Waves

### Wave 0: Documentation And Contract Lock

- Finalize this dev-plan.
- Update structured ingestion docs with node update/log terminology.
- Lock contracts for node logs, update plans, vector scopes, and summary
  refresh requests.
- Add contract tests only.

### Wave 1: Graph Log Storage

- Add `NodeActivityLog` graph model and registry support.
- Add write-plan support for activity log creation.
- Add deterministic validation and idempotency rules.
- Add graph service/repository methods to create and fetch node logs.
- Add tests proving logs are linked to target nodes and are not hidden metadata.

### Wave 2: Vector Scope Configuration

- Add first-class vector scope configuration.
- Split current vectorization into scope-aware builders.
- Add `memory_micro_logs` builder using compact log text.
- Add per-scope embedding model/dimension routing.
- Add tests for different dimensions and collection routing.

### Wave 3: Multi-Scope Retrieval And Hydration

- Query each enabled vector scope.
- Normalize and merge hits.
- Hydrate canonical graph targets from logs and context records.
- Render graph workspace results from hydrated targets, not raw vector hits.
- Add trace diagnostics showing scope, score, target, and hydration path.

### Wave 4: Node Summary Refresh

- Add summary refresh service.
- Implement trigger policy for recent logs and important context changes.
- Patch node summary fields through backend write services.
- Rebuild node-summary vectors when summaries change.
- Add UAT script to inspect logs, summaries, vectors, and hydration results for
  a target node.

### Wave 5: Agentic Update Tooling

- Add graph update tool/state for node updates.
- Use graph retrieval to resolve target candidates.
- Produce `NodeUpdatePlanDraft`.
- Ask clarification when target or update intent is ambiguous.
- Execute validated log creation, patches, summary refresh, and vector refresh.
- Return compact tool output to the invoking conversation state.

## Test And Acceptance Criteria

- Short node updates are stored as first-class semantic records.
- Node activity logs point back to graph targets and source provenance.
- Micro-log vector records hydrate to the target node and optional related
  context.
- Node summaries update only through explicit refresh logic.
- Node-summary embeddings refresh when summary checksums change.
- Multiple vector scopes can use different dimensions without mixing
  incompatible embeddings in one search call.
- Query-time retrieval can search multiple scopes and merge results
  deterministically.
- Raw edge-only embedding is not introduced as a default retrieval strategy.
- Agentic update flow returns one tool output and keeps user-facing responses
  non-technical.

## Open Decisions

- Final label name: `NodeActivityLog`, `MemoryLog`, or `NodeUpdateLog`.
- Whether node logs should always be Neo4j nodes, or whether some operational
  log rows may live only in the relational store. The baseline preference is
  Neo4j for semantic logs.
- Default dimensions for node summaries, contexts, and micro logs.
- Whether `ProfileMemory` belongs in `memory_contexts`,
  `memory_node_summaries`, or its own profile-memory scope.
- Which summary refresh triggers should run synchronously during ingestion and
  which should be background maintenance.
