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

## Locked Decisions

- `MemoryLog` is semantic graph memory stored as a lightweight Neo4j node.
- `MemoryLog` records are not stored as JSON arrays inside host domain nodes.
- A `MemoryLog` may be attached to multiple domain/context nodes.
- One `HAS_MEMORY_LOG` link may be marked `primary: true` for ranking,
  deduplication, and default UI anchoring.
- Media is stored as a `MediaAsset` node linked by edges, not as an inline
  domain-node or log attribute.
- V1 uses separate vector collections/scopes with one shared embedding
  dimension: `512`.
- V1 uses one query embedding to search all enabled collections.
- V1 explicitly passes `dimensions=512` for both document embeddings and query
  embeddings. Runtime environment defaults must not silently decide the vector
  shape for these scopes.
- V1 routes graph labels to vector scopes as follows:
  - `memory_node_summaries`: `Person`, `Place`, `Event`, `SocialCircle`;
  - `memory_contexts`: `Claim`, `Perception`, `RelationshipContext`,
    `RelationshipState`, `ProfileMemory`;
  - `memory_micro_logs`: `MemoryLog`.
- New v1 vector writes use the scoped collections only. The legacy
  `memory_documents` collection is not dual-written or dual-read by the new
  scope-aware path; existing records are treated as legacy until reindex.
- Prefix truncation from a larger embedding is not a v1 assumption. It may be
  evaluated later only for providers/models that explicitly support compatible
  shortened embeddings.
- Summary refresh is low priority and deferred until after log storage,
  micro-log vector retrieval, and UI navigation are stable.

## Vector DB Structure

The target vector structure should move from one generic collection toward
configured retrieval scopes.

V1 scope configuration:

```text
model: configured embedding model
dimensions: 512

collections:
  memory_node_summaries: 512 dimensions
  memory_contexts: 512 dimensions
  memory_micro_logs: 512 dimensions
```

Keeping the same dimension across collections allows one query embedding to be
reused safely for all enabled scopes. Collection separation still gives
different text builders, ranking weights, filters, and UI behavior.

### Embedding Policy

Embeddings are generated only from informational content that helps semantic
retrieval. Builder output must be deterministic, compact, and human-readable.

Include:

- concise memory facts, observations, corrections, preferences, and relationship
  context;
- stable domain summaries when the node has meaningful descriptive context;
- relevant time, kind, source kind, confidence, or original wording when those
  fields improve recall.

Exclude:

- raw UUIDs, graph payloads, metadata dumps, provider traces, prompts, tool-call
  payloads, backend audit details, and source documents in full;
- empty or label-only nodes;
- raw relationship edges without a memory-bearing record.

The vector scope config is the source of truth for embedding dimensions. Wave 2
must pass `dimensions=512` into `EmbeddingRequest` for document vectorization and
query embedding, even if provider or environment defaults also define an
embedding dimension.

### `memory_node_summaries`

Purpose:

- retrieve canonical graph nodes by their compact semantic summary.

Embeds:

- stable entity summaries;
- important aliases where supported;
- compact relationship or social context when present on or near the node;
- durable user-relevant facts.

Labels routed here in v1:

- `Person`;
- `Place`;
- `Event`;
- `SocialCircle`.

Primary target:

- the canonical graph node.

Related targets:

- important nearby `RelationshipContext`, `Perception`, `Event`, `Claim`, or
  `Source` records when useful.

Dimension strategy:

- v1 uses the shared `512` dimension.
- Future versions may test larger dimensions for this scope only if retrieval
  quality justifies generating per-scope query embeddings.

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

Labels routed here in v1:

- `MemoryLog`.

Primary target:

- the `MemoryLog` record itself.

Canonical target:

- the main domain/context node the log updates or describes, when there is one.

Related targets:

- involved domain nodes, relationship context, perception target, event/place
  context, source, and media attachments when available.

Dimension strategy:

- v1 uses the shared `512` dimension so the same query embedding can search all
  scopes.
- Future versions may test smaller micro-log dimensions only after the
  multi-scope retrieval and score-normalization path is stable.

### `memory_contexts`

Purpose:

- retrieve memory-bearing context records that are richer than raw edges but
  more specific than node summaries.

Embeds:

- `Perception`;
- `RelationshipContext`;
- `RelationshipState`;
- `Claim`;
- `ProfileMemory`.

Labels routed here in v1:

- `Claim`;
- `Perception`;
- `RelationshipContext`;
- `RelationshipState`;
- `ProfileMemory`.

Primary target:

- the context record.

Related targets:

- perceived target, relationship endpoints, source records, event/place
  context, and other supporting nodes.

Dimension strategy:

- v1 uses the shared `512` dimension.
- Future versions may test independent context dimensions if context retrieval
  needs different tuning from node summaries and micro logs.

### Query Across Multiple Scopes

V1 assumes all enabled scopes use the same embedding model and `512`
dimensions, so the retrieval layer generates one query embedding and searches
each collection with that same vector.

Example:

```text
query
  -> create one 512-dimensional query embedding
  -> search memory_node_summaries
  -> search memory_micro_logs
  -> search memory_contexts
  -> normalize and merge hits
  -> hydrate graph targets
  -> expand neighborhoods
  -> rank/render graph context
```

The retrieval response must expose enough diagnostics to explain which scope
produced each hit.

Wave 2 implements only the minimal raw multi-scope search path needed to prove
that one 512-dimensional query embedding can search every enabled v1 scope.
Score normalization, cross-scope merge, graph hydration, neighborhood expansion,
and folding `MemoryLog` hits into domain nodes remain Wave 3 work.

Future query strategies may include:

- `per_scope_embedding`: generate one embedding per distinct
  `(provider, model, dimensions)` tuple.
- `max_dimension_prefix_truncation`: generate the largest supported embedding
  once and use the first `N` dimensions for smaller scopes.

`max_dimension_prefix_truncation` is only valid when the embedding provider and
model explicitly support compatible shortened embeddings, and when indexed
documents and query embeddings use the same truncation policy.

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
- `primary_host_target_id`
- `primary_host_target_label`
- `host_target_ids`
- `involved_target_ids`
- `media_refs`
- `created_at`
- `updated_at`
- `lifecycle_state`
- `metadata`

Suggested relationships:

```text
(host)-[:HAS_MEMORY_LOG {primary: true|false, role: "..."}]->(log:MemoryLog)
(log)-[:INVOLVES {role: "..."}]->(target)
(log)-[:UPDATES_RELATIONSHIP]->(context:RelationshipContext)
(log)-[:HAS_MEDIA]->(asset:MediaAsset)
```

The log text must be short, human-readable, and semantically meaningful. It
should not be a raw source chunk, JSON payload, prompt trace, or provider log.

`primary_host_target_id` is the default UI anchor for the log. A log may still
be hosted by multiple domain/context nodes. For example, "I met Marco and Luca
at the seaside" may appear in both Marco's and Luca's timelines, while one host
link is marked `primary: true` for deduplication, ranking, and default
navigation.

`metadata` may store flexible backend/UI details for the log. The full timeline
must not be stored as a JSON array inside the host domain node.

## MediaAsset Model

Media is stored as a graph record linked to logs and domain/context nodes. It is
not a plain attribute on `MemoryLog` or the host node.

Working label:

- `MediaAsset`

Baseline fields:

- `id`
- `media_type`
- `mime_type`
- `storage_uri` or `storage_key`
- `checksum`
- `caption`
- `captured_at`
- `source_ids`
- `created_at`
- `updated_at`
- `lifecycle_state`
- `metadata`

Suggested relationships:

```text
(log:MemoryLog)-[:HAS_MEDIA {role: "evidence|attachment|memory_photo"}]->(media:MediaAsset)
(media)-[:DEPICTS {confidence: "..."}]->(domain_node)
(media)-[:CAPTURED_AT]->(place:Place)
(media)-[:CAPTURES_EVENT]->(event:Event)
```

`MemoryLogDraft.media_refs` may exist as an input placeholder. Persistence
should resolve media refs into `MediaAsset` records and graph edges once media
support is available.

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

Status: deferred, low priority.

Node summaries are compact derived views over durable memory records.
This remains part of the target architecture, but it is not part of the first
`MemoryLog` implementation slice. The immediate priority is to store logs
cleanly, vectorize them, retrieve them, hydrate their domain targets, and render
them in the UI.

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
- Lock contracts for `MemoryLog`, `MediaAsset` refs, update plans, and vector
  scopes.
- Add contract tests only.

### Wave 1: Graph MemoryLog Storage

Status: implemented in the graph storage/write-plan layer. This wave does not
implement vector scopes, prompt extraction, agentic update tooling, UI
navigation, or summary refresh.

- Add `MemoryLog` graph model and registry support.
- Add write-plan support for `MemoryLog` creation.
- Add deterministic validation and idempotency rules.
- Add graph service/repository methods to create and fetch memory logs.
- Add support for multiple host targets, one primary host, involved targets,
  relationship-context links, and media refs.
- Add `MediaAsset` graph model/registry support only as far as required for log
  links and future media storage.
- Add tests proving logs are linked to targets and are not hidden metadata.

### Wave 2: Vector Scope Configuration

- Add first-class vector scope configuration.
- Split current vectorization into scope-aware builders.
- Configure `memory_node_summaries`, `memory_contexts`, and
  `memory_micro_logs` with shared `512` dimensions for v1.
- Route v1 labels by scope:
  - `Person`, `Place`, `Event`, and `SocialCircle` to
    `memory_node_summaries`;
  - `Claim`, `Perception`, `RelationshipContext`, `RelationshipState`, and
    `ProfileMemory` to `memory_contexts`;
  - `MemoryLog` to `memory_micro_logs`.
- Remove the new path's dependency on the legacy `memory_documents` collection.
  Existing legacy records are ignored by scoped retrieval until reindex.
- Pass `dimensions=512` explicitly for document and query embeddings.
- Add `memory_micro_logs` builder using compact log text.
- Add collection routing and scope-specific ranking metadata.
- Add tests proving one 512-dimensional query embedding can search all v1
  scopes.
- Keep Wave 2 query-side behavior to raw per-scope search diagnostics. Do not
  implement score normalization, merged ranking, graph hydration, or default UI
  folding until Wave 3.

### Wave 3: Multi-Scope Retrieval And Hydration

- Query each enabled vector scope.
- Normalize and merge hits.
- Hydrate canonical graph targets from `MemoryLog` and context records.
- Fold `MemoryLog` and context hits only for default graph display target
  selection. Folding must not remove the matched record from the LLM-facing
  context.
- Preserve the exact matched record as retrieval evidence in the hydrated
  context. For example, a `Perception` hit about Alessandro must remain visible
  to the answer context even if the default graph renders Alessandro as the
  main domain node.
- Hydrate outward from both the matched record and the folded/display anchor.
  The retrieval goal is to build a contextual answer package, not merely to
  identify one exact node.
- Render graph workspace results from hydrated domain targets, not raw vector
  hits.
- Add trace diagnostics showing scope, score, target, and hydration path.
- Add optional target-constrained retrieval. A caller may provide graph target
  ids to focus a semantic query around known anchors, such as searching for
  "oppressive" only in Alessandro's surrounding memory context.
- Implement target constraints by graph expansion and post-vector filtering in
  v1: resolve the target ids, expand an allowed graph set from nearby memories
  and context records, run scoped vector search, then keep hits whose primary,
  canonical, related, or hydrated targets intersect the allowed set. Do not rely
  on vector-store metadata filtering as the only constraint mechanism.
- Keep v1 score normalization intentionally simple:
  `normalized_score = 1 / (1 + distance) * scope_weight`, with all v1 scope
  weights initially set to `1.0`.
- Add a TODO/evaluation note to revisit scope weights and score normalization
  after UAT data exists.
- Do not leave a second deprecated hydrated retrieval service in production
  code. Wave 3 may reuse or reshape the old single-collection search logic, but
  the final production path should be one scoped hydrated retrieval service,
  plus the raw scope-search endpoint only if it remains useful as debug/UAT
  tooling.

Hydration/folding policy:

```text
MemoryLog hit
  -> matched MemoryLog remains in LLM context
  -> default graph display target is canonical/primary host
  -> hydrate host, involved nodes, relationship contexts, nearby logs, and media/source refs

Perception hit
  -> matched Perception remains in LLM context
  -> default graph display target is the perceived domain target
  -> hydrate target, relationship context, related perceptions, claims, and memory logs

RelationshipContext hit
  -> matched context remains in LLM context
  -> default graph display targets are relationship endpoints/domain anchors
  -> hydrate states, perceptions, logs, claims, and relevant events/places

RelationshipState hit
  -> matched state remains in LLM context
  -> default graph display targets are the parent relationship context endpoints
  -> hydrate parent context and nearby relationship history

Claim hit
  -> matched Claim remains in LLM context
  -> default graph display targets are related/about domain nodes when available
  -> hydrate supporting, contradicting, and neighboring context when present

ProfileMemory hit
  -> matched profile record remains in LLM context
  -> default graph display target is the owner/user Person when linked
  -> otherwise keep the profile record as context fallback
```

### Wave 4: UI MemoryLog Navigation

- Render default search output as domain nodes and domain relationships.
- Add dedicated read APIs for `MemoryLog` navigation:
  `GET /graph/nodes/{node_id}/memory-logs` and
  `GET /graph/memory-logs/{log_id}`.
- Execute log filters in the backend for time range, log kind, source kind,
  involved target, media-only, archived inclusion, and limit.
- Preserve graph state while entering/exiting a domain node's iceberg view;
  focusing a selected node's neighborhood is an explicit action.
- Show `MemoryLog` history as a nested timeline in node detail using reusable
  frontend components for filters, rows, timeline, detail, retrieval evidence,
  and diagnostics.
- Expand a selected log into hosts, involved nodes, relationship contexts,
  media refs, and relationships. Full media preview remains future work.
- Start debug/UAT support with diagnostics panels for matched records, scopes,
  scores, roles, and hydration paths. Do not render logs as graph nodes by
  default.

### Wave 5: Agentic Update Tooling

- Add graph update tool/state for node updates.
- Use graph retrieval to resolve target candidates.
- Produce `NodeUpdatePlanDraft`.
- Ask clarification when target or update intent is ambiguous.
- Execute validated `MemoryLog` creation, safe patches, and vector refresh.
- Update reasoning/planning/extraction prompts with domain-node versus
  `MemoryLog` definitions, rules, and few-shot examples.
- Return compact tool output to the invoking conversation state.

### Deferred Wave: Node Summary Refresh

- Add summary refresh service.
- Implement trigger policy for recent logs and important context changes.
- Patch node summary fields through backend write services.
- Rebuild node-summary vectors when summaries change.
- Add UAT script to inspect logs, summaries, vectors, and hydration results for
  a target node.

## Test And Acceptance Criteria

- Short updates are stored as first-class `MemoryLog` records.
- `MemoryLog` records point back to multiple possible host targets, exactly one
  primary host target when more than one host exists, involved targets, source
  provenance, and optional media links.
- Media attachments are represented through `MediaAsset` records and
  relationships, not inline node/log attributes.
- Micro-log vector records hydrate to the host/canonical domain node and
  optional related context.
- V1 vector scopes use one shared `512` dimension and one query embedding across
  `memory_node_summaries`, `memory_contexts`, and `memory_micro_logs`.
- `EmbeddingRequest` receives `dimensions=512` explicitly for v1 document and
  query embedding calls.
- Scoped v1 vectorization does not dual-write to `memory_documents`, and scoped
  v1 search does not dual-read from `memory_documents`.
- Embedding text is informational only and excludes raw IDs, graph payloads,
  metadata dumps, provider traces, prompts, and backend audit details.
- Default graph search output renders domain nodes, not raw logs.
- Folding a `MemoryLog`, `Perception`, `RelationshipContext`,
  `RelationshipState`, `Claim`, or `ProfileMemory` hit into a display target
  must not remove the matched record from the LLM-facing hydrated context.
- Hydrated retrieval context includes both the matched vector record target and
  the surrounding graph context needed to answer the user, such as domain nodes,
  relationship contexts, states, perceptions, related logs, claims, events,
  places, source refs, and media refs when available.
- Target-constrained retrieval can focus semantic search around supplied graph
  target ids by expanding graph context and filtering scoped vector hits against
  the allowed target set.
- Clicking a domain node can transition into a navigable `MemoryLog` history and
  return to the prior domain graph output.
- Node summary refresh is deferred and must not be treated as required for the
  first `MemoryLog` implementation slice.
- Future multi-dimension retrieval must not mix incompatible embeddings in one
  collection or search call.
- Query-time retrieval can search multiple scopes and merge results
  deterministically.
- Raw edge-only embedding is not introduced as a default retrieval strategy.
- Agentic update flow returns one tool output and keeps user-facing responses
  non-technical.
- Prompt tests/examples prove the model distinguishes domain nodes from
  `MemoryLog` records.

## Open Decisions

- Exact summary refresh trigger policy, once the deferred summary-refresh wave is
  reopened.
- Whether future retrieval should move from shared `512` dimensions to
  per-scope dimensions, provider-supported prefix truncation, or another
  strategy after UAT/evaluation.
