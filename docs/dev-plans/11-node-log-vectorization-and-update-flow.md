# MemoryLog Vectorization And Node Update Flow

## Summary

Define the next retrieval and update architecture for lightweight `MemoryLog`
records, multi-scope vector storage, node summary refresh, UI log navigation,
and agentic graph update flows.

This plan extends the graph-RAG baseline. Neo4j remains the source of truth for
memory records, relationships, provenance, lifecycle, and audit history. Vector
stores remain retrieval indexes that point back to authoritative graph records.

The key refinement is to stop treating every retrieval unit as a full domain
node summary. Stable domain nodes are the visible peaks of the memory graph.
`MemoryLog` records are lightweight memory atoms below those peaks: small
dated pieces of user memory that may involve one or more nodes, relationships,
or media attachments. They are important in aggregate, are retrievable through
compact embeddings, and can drive node summary refreshes without inflating the
domain node itself.

## Current Baseline

Current ingestion stores memory in these forms:

- entity nodes, such as `Person`, `Place`, `Event`, `SocialCircle`;
- memory-bearing context nodes, such as `Perception`, `RelationshipContext`,
  `RelationshipState`, `Claim`, and `ProfileMemory`;
- typed graph relationships between nodes;
- metadata patches on existing nodes;
- backend `ChangeRecord` nodes for change/audit history.

Important limitation:

- There is no first-class semantic `MemoryLog` today.
- `ChangeRecord` is backend change history. It should not be used as the user
  memory log surface.
- Metadata patches can append values to node properties, but that is not a
  retrieval-friendly or maintainable log model.
- Current vectorization uses the `memory_documents` collection with typed
  embedding documents built from graph records.
- Embedding dimension is currently available at request/provider level, but
  there is no first-class per-scope vector configuration yet.

## Design Principles

- Distinguish visible domain nodes from lightweight memory atoms.
- Domain nodes represent stable identities or durable graph objects: people,
  places, events, organizations, objects, animals, social circles, topics, and
  other first-class graph concepts.
- `MemoryLog` records represent small dated memories, updates, observations, or
  contextual facts that compose one or more domain/context nodes.
- A `MemoryLog` can be a graph record without being rendered as a normal graph
  node in the default UI.
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
- The graph workspace should show domain nodes by default. `MemoryLog` records
  are nested timeline/detail data unless the user enters a dedicated log view or
  debug/UAT mode.

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

- retrieve precise short user-stated memory atoms and route them back to the
  domain/context nodes they compose.

Embeds:

- short `MemoryLog` records;
- corrections;
- short facts;
- observations;
- status updates;
- preferences or profile updates when represented as node-targeted logs.

Primary target:

- the `MemoryLog` record itself.

Canonical target:

- the main domain/context node the log updates or describes, when there is one.

Related targets:

- involved domain nodes, relationship context, perception target, event/place
  context, source, and media attachments when available.

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

## MemoryLog Model

Add a first-class semantic log record for user-relevant memory atoms.

Working label:

- `MemoryLog`

Alternative names to consider only if `MemoryLog` proves too generic:

- `MemoryFragment`
- `MemoryAtom`
- `NodeUpdateLog`

Baseline fields:

- `id`
- `log_text`
- `log_kind`
- `source_kind`
- `source_ids`
- `extraction_run_ids`
- `original_user_words`
- `temporal_scope`
- `happened_at`
- `confidence`
- `importance`
- `host_target_id`
- `host_target_label`
- `involved_target_ids`
- `media_refs`
- `created_at`
- `updated_at`
- `lifecycle_state`
- `metadata`

Suggested relationships:

```text
(host)-[:HAS_MEMORY_LOG]->(log:MemoryLog)
(log)-[:INVOLVES {role: "..."}]->(target)
(log)-[:UPDATES_RELATIONSHIP]->(context:RelationshipContext)
(log)-[:HAS_MEDIA]->(asset:MediaAsset)
```

The log text must be short, human-readable, and semantically meaningful. It
should not be a raw source chunk, JSON payload, prompt trace, or provider log.

The `host_target_id` is the primary UI anchor for the log. A log may still
involve multiple nodes. For example, "I met Marco and Luca at the seaside" may
be hosted under Marco because the current user was looking at Marco, while also
linking Luca and the seaside place through `INVOLVES` relationships.

`metadata` may store flexible backend/UI details for the log. The full timeline
must not be stored as a JSON array inside the host domain node.

## Domain Node And MemoryLog Separation

Use this mental model:

```text
Domain node = stable identity / aggregate memory surface
MemoryLog = small dated memory brick
Perception = subjective view
RelationshipContext = durable relation container
RelationshipState = temporal state of a relationship
MediaAsset = attachment/supporting artifact
Vector record = retrieval index pointing back to one of these
```

A `MemoryLog` is "node-like" for storage, lifecycle, provenance, media
attachment, and vector retrieval. It is not "node-like" in the default graph
workspace. The default graph should render stable domain nodes and their
relationships; logs are nested under the relevant domain/context view.

## UI Fruition Model

The graph workspace should communicate the iceberg model:

- the visible graph is the domain layer;
- each domain node is the peak of a larger underlying memory history;
- `MemoryLog` records are the dated, navigable memory layer below that node;
- relationship and perception contexts are richer supporting layers, not raw
  visual clutter.

Default query behavior:

```text
search query
  -> retrieve hits across node summaries, micro logs, and contexts
  -> hydrate graph targets
  -> fold MemoryLog hits into their host/canonical domain nodes
  -> render domain nodes and domain relationships in the graph workspace
```

Domain node click behavior:

```text
domain graph output
  -> click domain node
  -> transition into node detail / iceberg view
  -> show summary peak, key relationships, and MemoryLog timeline below
  -> allow log navigation, filters, media preview, and context expansion
  -> exit detail view
  -> return to the previous domain graph output and layout state
```

UI rules:

- Default search results should not render `MemoryLog` records as ordinary
  graph nodes.
- A log hit should strengthen or reveal its host domain node in the graph
  result.
- The node detail view should show logs as a timeline or navigable history,
  grouped by time, kind, source, or involved nodes.
- Logs may expand into attached media, source wording, involved entities, or
  relationship/perception context.
- Debug/UAT views may show `MemoryLog` records as graph nodes to inspect
  storage and retrieval behavior.
- The graph workspace should preserve the domain graph layout when entering and
  exiting a domain node's memory-log view.

## Node Update Flow

### Existing Node Update

```text
source message
  -> graph retrieval for candidate target nodes
  -> reasoning checkpoint
  -> update plan
  -> target resolution
  -> deterministic validation
  -> write MemoryLog
  -> apply explicit field patches only when safe
  -> vectorize micro log
  -> refresh node summary if trigger fires
  -> refresh node-summary embedding if summary changed
  -> return compact tool output
```

The default action for new user-stated facts about an existing node should be a
`MemoryLog` record, not an immediate destructive overwrite of node fields.

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
  -> optionally create initial MemoryLog
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

- recent `MemoryLog` records;
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

## Prompt And Extraction Rules

Reasoning, planning, and extraction prompts must teach the model to split
domain nodes from `MemoryLog` records.

Definitions to include in prompt guidelines:

- A domain node is a stable entity or aggregate object that can accumulate
  memory over time.
- A `MemoryLog` is a short dated memory fragment, update, observation, or
  contextual detail involving one or more domain/context nodes.
- A `MemoryLog` can support retrieval and future summarization without becoming
  a visible graph-domain node.

Rules:

- Do not create a new domain node for a small update about an existing person,
  place, object, relationship, or topic.
- Attach the update to the resolved domain/context node as a `MemoryLog`.
- Create a domain node only when the text introduces a durable entity or object
  that may be referenced again.
- Create an `Event` only when the happening has independent event identity,
  relevant participants/place/time, or is likely to be queried as an event.
- Create a `RelationshipContext` when the memory describes a durable
  relationship, emotional relationship context, or relationship history.
- Create or update a `RelationshipState` when the text changes the current
  state of an existing relationship context.
- A `MemoryLog` may coexist with a field patch, relationship context, perception,
  or media attachment when the source wording is worth preserving as dated
  story.
- Use clarification when the host domain node or update target is ambiguous.

Few-shot prompt examples:

```text
Input: "Ho visto Marco ieri, mi ha detto che ha cambiato lavoro."
Output intent:
- Resolve/create domain node: Person Marco.
- Create MemoryLog hosted by Marco: "Marco said yesterday that he changed job."
- Do not create a new Event unless the meeting itself is important in context.
```

```text
Input: "Mio fratello Matteo ora vive a Torino."
Output intent:
- Resolve/create domain node: Person Matteo.
- Preserve brother relationship to the owner as relationship context or typed
  relationship.
- Create MemoryLog hosted by Matteo: "Matteo now lives in Turin."
- Patch stable location only if validation policy allows it.
```

```text
Input: "Con Luca siamo diventati più distanti dopo quel viaggio."
Output intent:
- Resolve/create domain node: Person Luca.
- Resolve/create RelationshipContext between owner and Luca.
- Create/update RelationshipState: lower closeness / more distant.
- Create MemoryLog linked to the relationship context and Luca preserving the
  dated story.
```

```text
Input: "Ho una foto con Anna al mare l'estate scorsa."
Output intent:
- Resolve/create domain node: Person Anna.
- Create MemoryLog hosted by Anna or by the relevant event/place context.
- Attach MediaAsset when the photo is available.
- Link involved place/event context if known.
```

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
  -> backend writes MemoryLogs and graph changes
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
- `MemoryLog` records created;
- fields patched;
- summaries refreshed;
- vector scopes refreshed;
- clarification needed, if any;
- concise diagnostics for the next model call.

User-facing responses should stay simple and non-technical. Internal tool
outputs may include technical detail when the next state needs it.

## Contracts To Add

Planned lightweight contracts:

- `MemoryLogDraft`
- `MemoryLog`
- `MemoryLogLinkDraft`
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
- Update structured ingestion docs with `MemoryLog` terminology.
- Lock contracts for `MemoryLog`, update plans, vector scopes, and summary
  refresh requests.
- Add contract tests only.

### Wave 1: Graph MemoryLog Storage

- Add `MemoryLog` graph model and registry support.
- Add write-plan support for `MemoryLog` creation.
- Add deterministic validation and idempotency rules.
- Add graph service/repository methods to create and fetch memory logs.
- Add support for host target, involved targets, relationship-context links, and
  media refs.
- Add tests proving logs are linked to targets and are not hidden metadata.

### Wave 2: Vector Scope Configuration

- Add first-class vector scope configuration.
- Split current vectorization into scope-aware builders.
- Add `memory_micro_logs` builder using compact log text.
- Add per-scope embedding model/dimension routing.
- Add tests for different dimensions and collection routing.

### Wave 3: Multi-Scope Retrieval And Hydration

- Query each enabled vector scope.
- Normalize and merge hits.
- Hydrate canonical graph targets from `MemoryLog` and context records.
- Fold `MemoryLog` hits into domain node graph results by default.
- Render graph workspace results from hydrated domain targets, not raw vector
  hits.
- Add trace diagnostics showing scope, score, target, and hydration path.

### Wave 4: Node Summary Refresh

- Add summary refresh service.
- Implement trigger policy for recent logs and important context changes.
- Patch node summary fields through backend write services.
- Rebuild node-summary vectors when summaries change.
- Add UAT script to inspect logs, summaries, vectors, and hydration results for
  a target node.

### Wave 5: UI MemoryLog Navigation

- Render default search output as domain nodes and domain relationships.
- Preserve graph state while entering/exiting a domain node's iceberg view.
- Show `MemoryLog` history as a nested timeline in node detail.
- Add log filters by time, kind, source, involved nodes, and media.
- Support debug/UAT rendering where logs can be shown as graph records.

### Wave 6: Agentic Update Tooling

- Add graph update tool/state for node updates.
- Use graph retrieval to resolve target candidates.
- Produce `NodeUpdatePlanDraft`.
- Ask clarification when target or update intent is ambiguous.
- Execute validated `MemoryLog` creation, patches, summary refresh, and vector
  refresh.
- Update reasoning/planning/extraction prompts with domain-node versus
  `MemoryLog` definitions, rules, and few-shot examples.
- Return compact tool output to the invoking conversation state.

## Test And Acceptance Criteria

- Short updates are stored as first-class `MemoryLog` records.
- `MemoryLog` records point back to host targets, involved targets, source
  provenance, and optional media.
- Micro-log vector records hydrate to the host/canonical domain node and
  optional related context.
- Default graph search output renders domain nodes, not raw logs.
- Clicking a domain node can transition into a navigable `MemoryLog` history and
  return to the prior domain graph output.
- Node summaries update only through explicit refresh logic.
- Node-summary embeddings refresh when summary checksums change.
- Multiple vector scopes can use different dimensions without mixing
  incompatible embeddings in one search call.
- Query-time retrieval can search multiple scopes and merge results
  deterministically.
- Raw edge-only embedding is not introduced as a default retrieval strategy.
- Agentic update flow returns one tool output and keeps user-facing responses
  non-technical.
- Prompt tests/examples prove the model distinguishes domain nodes from
  `MemoryLog` records.

## Open Decisions

- Final relationship names for host, involvement, relationship-update, and
  media links.
- Whether `MemoryLog` records should always be Neo4j nodes, or whether some
  operational logs may live only in the relational store. The baseline
  preference is Neo4j for semantic memory logs.
- Default dimensions for node summaries, contexts, and micro logs.
- Whether `ProfileMemory` belongs in `memory_contexts`,
  `memory_node_summaries`, or its own profile-memory scope.
- Which summary refresh triggers should run synchronously during ingestion and
  which should be background maintenance.
