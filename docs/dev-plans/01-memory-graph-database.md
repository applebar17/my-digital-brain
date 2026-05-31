# Memory Graph Database Definition

## Goal

Define the local graph database that stores memories, entities, relationships, claims, sources, profile memories, metadata, provenance, and queryable structure for Graph-RAG.

The graph database is the canonical memory store. It should be rich enough from v1 to preserve provenance, uncertainty, time, lifecycle, privacy, and affective memory, while keeping the number of entity classes controlled.

## Design Stance

- Prefer a rich core schema over many premature node classes.
- Keep source evidence and provenance first-class.
- Use direct relationships for high-confidence graph structure.
- Use `Claim` nodes for uncertain, disputed, temporal, or evidence-heavy facts.
- Use `Perception` and `RelationshipContext` nodes for subjective and emotionally meaningful memory attached to any relevant target, not only people.
- Preserve emotional summaries and original user wording as first-class memory fields on memory-bearing nodes and important relationships when present.
- Keep arbitrary metadata available, but promote important metadata into typed properties, relationships, or dedicated nodes.
- Use app-generated persistent IDs internally, but expose simplified temporary aliases to LLM contexts.
- Use a relational operational store from the beginning for app/session/source/provider/runtime data that does not belong in the graph.
- Use a separate vector database through a protocolled interface rather than coupling embeddings to Neo4j.
- Protect the running graph with authentication and private networking.
- Protect graph copies, dumps, and backups with encrypted export packages.

## Locked Decisions

- Graph database: Neo4j.
- Operational relational store: include from v1, local or remote.
- Schema philosophy: controlled rich core.
- Complex fact modeling: use `Claim` nodes for uncertain, disputed, temporal, or evidence-heavy facts.
- Affective memory modeling: use `Perception` and `RelationshipContext` nodes from v1.
- Emotional fields: include `emotional_summary`, `emotional_valence`, `emotional_intensity`, `emotion_tags`, and `original_user_words` where relevant on nodes and relationships.
- Internal ID strategy: app-generated UUIDs.
- LLM-facing ID strategy: simplified aliases mapped per context, such as `NODE_000001`, `REL_000001`, `CLAIM_000001`, and `SOURCE_000001`.
- Vector storage: separate vector database behind a protocolled interface.
- Local vector option: Chroma.
- Cloud vector option: Azure AI services through the vector store protocol.
- Metadata policy: governed metadata with promotion rules.
- Temporal model: full temporal model from v1.
- Trust, privacy, and lifecycle enums: use the current baseline enum sets.
- Backup security: encrypted backup package.
- Migration strategy: versioned migrations.

## Wave 0: Baseline Decisions

- Use Neo4j as the MVP graph database.
- Add a relational operational store from the beginning, preferably Postgres-compatible, with local and remote deployment options.
- Define graph schema v1 with rich fields but controlled node classes.
- Decide where source artifacts live: graph references plus local source/media storage.
- Store embeddings in a separate vector database behind a `VectorStore` protocol.
- Support Chroma locally and Azure AI services in cloud mode through that protocol.
- Use app-generated UUIDs for entities, relationships, sources, claims, extraction runs, vector records, relational records, and export packages.
- Use LLM-facing temporary ID aliases when building model context.
- Enable graph database authentication from the beginning.
- Keep the graph database reachable only from the backend/container network unless explicitly exposed for local debugging.
- Decide migration approach for schema constraints and indexes.

## Store Responsibilities

### Neo4j Graph Store

Canonical memory graph:

- Entities.
- Relationships.
- Claims.
- Perceptions.
- Relationship contexts.
- Profile memories.
- Contact points.
- External references.
- Graph provenance references.
- Queryable memory structure.

### Relational Operational Store

Operational application state:

- Telegram chats and user allowlist.
- Pending ingestion sessions.
- Source records and source metadata.
- Provider request logs.
- Model/prompt/schema version registry.
- Background job state.
- Vector record references.
- Backup/export records.
- Audit entries that are easier to query relationally.

The relational store may be local for MVP or remote later. It should not replace the graph as the canonical memory model.

### Source And Media Storage

Large artifacts:

- Original voice/audio files.
- Transcript files.
- Uploaded documents.
- Images.
- Export packages.

The graph and relational store should reference these artifacts rather than storing large payloads inline.

### Vector Store

Embedding search:

- Source chunks.
- Entity descriptions.
- Claim text.
- Event summaries.
- Perception descriptions.
- Relationship context summaries.
- Graph neighborhood summaries.

The application should use a `VectorStore` protocol so Chroma can be used locally and Azure AI services can be used in cloud mode.

## ID Strategy

Internal persistent IDs should be app-generated UUIDs. They are stable, portable across backups, and safe for migrations and replay.

LLM contexts should not expose long opaque IDs directly when avoidable. Before sending graph context to a model, the context builder should create a temporary alias map:

```text
UUID 8f1f7c3a-... -> NODE_000001
UUID 2ab93b1d-... -> NODE_000002
UUID 17dc7a91-... -> CLAIM_000001
UUID 72ad38f4-... -> SOURCE_000001
```

The model should reference aliases in structured outputs. The backend maps aliases back to internal UUIDs before validation and graph writes.

Benefits:

- Reduces token usage.
- Reduces ID copy mistakes.
- Makes prompts and tool calls easier for the model.
- Improves human debugging of model outputs.

Rules:

- Alias maps are scoped to one model context or process step.
- Aliases are not persisted as canonical IDs.
- Structured model outputs must be resolved back to UUIDs before graph operations.
- Failed alias resolution should fail validation rather than guess.

## Wave 1: MVP Graph Schema

### Core Node Types

Implement these node types first:

- `Person`
- `Event`
- `Place`
- `Organization`
- `Object`
- `Topic`
- `Source`
- `Claim`
- `Perception`
- `RelationshipContext`
- `ProfileMemory`
- `ContactPoint`
- `ExternalReference`
- `ExtractionRun`

Optional support nodes:

- `SchemaVersion`
- `GraphExport`
- `MergeRecord`

### Common Node Properties

Most memory-bearing nodes should include:

- `id`
- `created_at`
- `updated_at`
- `description`
- `confidence`
- `trust_level`
- `privacy_level`
- `lifecycle_state`
- `metadata`

Affective fields should be available on every emotionally meaningful node and important relationship:

- `emotional_summary`
- `emotional_valence`
- `emotional_intensity`
- `emotion_tags`
- `original_user_words`

Recommended common enum values:

- `trust_level`: user_confirmed, source_stated, llm_inferred, system_derived, externally_enriched, contradicted, stale.
- `privacy_level`: normal, private, sensitive, local_only, hidden.
- `lifecycle_state`: candidate, active, confirmed, inferred, disputed, stale, expired, archived, deleted.

### Type-Specific Properties

`Person`:

- `display_name`
- `normalized_name`
- `aliases`
- `known_since`
- `status`

`Event`:

- `title`
- `started_at`
- `ended_at`
- `time_precision`
- `original_time_text`

`Place`:

- `name`
- `normalized_name`
- `address`
- `city`
- `region`
- `country`
- `latitude`
- `longitude`
- `place_precision`

`Organization`:

- `name`
- `normalized_name`
- `aliases`
- `domain`

`Object`:

- `name`
- `category`
- `owner_hint`

`Topic`:

- `name`
- `normalized_name`
- `aliases`

`Source`:

- `source_type`
- `channel`
- `external_id`
- `source_created_at`
- `received_at`
- `content_ref`
- `transcript_ref`
- `derived_from_source_id`
- `checksum`

`Claim`:

- `text`
- `claim_type`
- `valid_from`
- `valid_to`
- `observed_at`
- `source_time`
- `time_precision`

`Perception`:

- `description`
- `perception_type`
- `target_type`
- `emotional_valence`
- `emotional_intensity`
- `emotion_tags`
- `original_user_words`
- `source_kind`
- `valid_from`
- `valid_to`
- `time_precision`

`RelationshipContext`:

- `description`
- `relationship_type`
- `status`
- `closeness`
- `emotional_summary`
- `emotional_valence`
- `emotional_intensity`
- `emotion_tags`
- `original_user_words`
- `valid_from`
- `valid_to`
- `time_precision`

`Perception` and `RelationshipContext` are not person-only concepts. A `Perception` may target a place, event, object, topic, organization, source, claim, profile memory, or relationship context. A `RelationshipContext` should be used whenever a relationship itself has enough emotional, temporal, or evidential weight to become a memory object.

`ProfileMemory`:

- `profile_key`
- `category`
- `value`
- `stability`
- `visibility`

`ContactPoint`:

- `kind`
- `value`
- `normalized_value`
- `label`
- `valid_from`
- `valid_to`
- `is_primary`

`ExternalReference`:

- `provider`
- `external_id`
- `url`
- `label`
- `retrieved_at`
- `expires_at`

`ExtractionRun`:

- `source_id`
- `processor`
- `processor_version`
- `model`
- `prompt_version`
- `schema_version`
- `started_at`
- `completed_at`
- `status`

### Relational Baseline Tables

The exact relational schema can evolve during coding, but the baseline store should support:

- `telegram_chats`
- `ingestion_sessions`
- `source_records`
- `provider_request_logs`
- `model_registry`
- `prompt_registry`
- `schema_registry`
- `background_jobs`
- `vector_records`
- `backup_exports`
- `audit_log`

The relational store is allowed to reference graph UUIDs, but it should not become the canonical memory graph.

### Core Relationship Types

Implement these relationships first:

- `MENTIONED_IN`: Entity to Source.
- `SUPPORTED_BY`: Claim to Source.
- `DERIVED_FROM`: Entity, Claim, Source, or ProfileMemory to Source or ExtractionRun.
- `PARTICIPATED_IN`: Person to Event.
- `HAPPENED_AT`: Event to Place.
- `ABOUT`: Source or Claim to Topic.
- `RELATED_TO`: Generic weakly typed relationship.
- `HAS_CONTACT_POINT`: Person or Organization to ContactPoint.
- `HAS_EXTERNAL_REFERENCE`: Entity to ExternalReference.
- `DESCRIBES_USER`: ProfileMemory to Person.
- `CONTRADICTS`: Claim to Claim.
- `PERCEIVES`: User/Person to Perception.
- `PERCEPTION_OF`: Perception to any memory-bearing target entity or relationship context.
- `HAS_RELATIONSHIP_CONTEXT`: User/Person to RelationshipContext.
- `RELATIONSHIP_WITH`: RelationshipContext to any target entity.
- `HAS_AFFECTIVE_CONTEXT`: Entity, Claim, Source, or RelationshipContext to Perception when affective context needs to be explicit and queryable.

Common relationship properties:

- `id`
- `created_at`
- `updated_at`
- `confidence`
- `trust_level`
- `privacy_level`
- `lifecycle_state`
- `valid_from`
- `valid_to`
- `emotional_summary`
- `emotional_valence`
- `emotional_intensity`
- `emotion_tags`
- `original_user_words`
- `source_ids`
- `extraction_run_ids`
- `metadata`

Important Neo4j constraint: relationships cannot have outgoing relationships to evidence nodes. For v1, relationship provenance can be stored through `source_ids`, `extraction_run_ids`, and metadata. When a relationship needs richer evidence, contradiction handling, temporal nuance, or affective history, represent the fact as a `Claim` or `RelationshipContext` node linked to sources.

### Constraints And Indexes

Wave 1 should create constraints for:

- Unique IDs per node label.
- Unique `Source` by `(channel, external_id)` where available.
- Unique `ExternalReference` by `(provider, external_id)` where available.
- Unique `ExtractionRun.id`.
- Unique IDs for `Perception` and `RelationshipContext`.

Wave 1 should create indexes for:

- Person normalized name and aliases.
- Place normalized name, city, country.
- Event started_at and ended_at.
- Source channel, external_id, received_at.
- Claim claim_type, valid_from, valid_to.
- Perception perception_type, emotional_valence.
- RelationshipContext relationship_type, status, closeness.
- lifecycle_state.
- privacy_level.
- trust_level.

Full-text or vector indexes can be added for:

- Entity descriptions.
- Source/transcript text.
- Claim text.
- Perception descriptions and original user words.
- RelationshipContext descriptions and emotional summaries.
- Event summaries.
- Affective summaries attached to places, events, objects, topics, organizations, claims, sources, and important relationships.

Vector indexes should be managed in the external vector store rather than Neo4j for v1. Neo4j may still have full-text indexes for graph-native lookup.

## Wave 2: Rich Memory Semantics

Wave 2 should stay graph-focused. The goal is to make the graph behave like a memory system with time, current state, history, relationship evolution, contradiction representation, merge auditability, and affective provenance.

Locked Wave 2 implementation decisions:

- Do not implement the contradiction judge agent or judge invocation flow in Wave 2.
- Add `ChangeRecord`.
- Store current state directly on the main node, relationship, `Perception`, or `RelationshipContext`.
- Preserve history underneath through graph records.
- Attach `RelationshipState` only to `RelationshipContext`, not directly to bare relationships.
- Add service/API support for `ContradictionRecord`.
- Add service/API support for `MergeRecord`.
- Implement entity merge as an auditable, non-destructive graph operation.
- Create a `ChangeRecord` for every explicit lifecycle transition.

### Temporal Semantics

Add deterministic time fields that preserve both the user's original expression and the resolved queryable range:

- `original_time_text`: the user/source expression, such as `yesterday`, `last summer`, or `during university`.
- `resolved_start`: ISO date or datetime when the time starts.
- `resolved_end`: ISO date or datetime when the time ends.
- `time_precision`: exact, day, month, year, season, period, range, unknown.
- `time_basis`: conversation_at, source_created_at, user_stated, inferred, external_metadata.
- `timezone`: IANA timezone when relevant, such as `Europe/Rome`.

Do not ask LLMs to provide numeric confidence for time inference in v1. Instead, preserve `time_basis`, `time_precision`, and `original_time_text` so the system can reason about reliability without fake precision.

Future ingestion should use a dedicated temporal inference pipeline when the date is uncertain. That pipeline can receive conversation time, source time, user locale/timezone, prior context, and external calendar/source metadata, then return the same structured temporal fields.

### Current State Plus History

Expose current state by default, but preserve the historical log underneath.

Example current layer:

```text
Alessandro: low contact now, historically close, emotionally mixed.
```

Example history layer:

```text
2010-2015: close friendship.
2020 onward: low contact.
User-stated perception: some traits felt oppressive.
Later update: relationship softened after reconnecting.
```

Implementation stance:

- Current fields live on the main node, relationship, `Perception`, or `RelationshipContext`.
- Historical changes are preserved as `Claim`, `Perception`, `RelationshipContext`, `RelationshipState`, or `ChangeRecord` graph records.
- Important previous values are not overwritten without preserving the old state.
- Query APIs should return current facts by default and history only when requested.
- Current state is stored directly for simple querying; it is not dynamically recomputed from history on every read in Wave 2.

### Relationship State History

Simple facts should remain simple edges. Example: `Person` `WORKS_AT` `Organization`, or `Event` `HAPPENED_AT` `Place`.

Complex relationships need a diary-like model capable of storing many states over time with low restriction. A long relationship with an ex, close friend, family member, project, or organization can move through many states across years. The graph must preserve those state changes without forcing a rigid relationship taxonomy.

Recommended model:

- `RelationshipContext`: the stable relationship memory object.
- `RelationshipState`: a dated state entry belonging to a relationship context.
- `HAS_RELATIONSHIP_STATE`: RelationshipContext to RelationshipState.
- `RELATIONSHIP_WITH`: RelationshipContext to the target entity.

`RelationshipState` should not attach directly to a bare edge. If a relationship needs state history, it is complex enough to be represented as a `RelationshipContext`.

`RelationshipState` should support:

- `description`
- `status`
- `closeness`
- `emotional_summary`
- `emotional_valence`
- `emotion_tags`
- `original_user_words`
- temporal fields
- lifecycle/privacy/trust fields
- source references
- metadata

This lets the graph store entries like:

- Date X: "we were very close".
- Date Y: "we broke up and stopped talking".
- Date Z: "we met again and things felt calmer".

The states can be detailed or sparse. The important point is that each state is a preserved memory slice.

### Lifecycle Transitions

Add explicit lifecycle transition handling for nodes, relationships, claims, perceptions, relationship contexts, and relationship states:

- active
- confirmed
- inferred
- disputed
- stale
- expired
- archived
- deleted

Lifecycle transitions should preserve source evidence, actor, timestamp, reason, and previous state when meaningful.

Every explicit lifecycle transition should create a `ChangeRecord`.

### Change Records

Add `ChangeRecord` as the generic audit record for updates that are not naturally represented as claims, perceptions, relationship states, contradiction records, or merge records.

Use `ChangeRecord` for:

- Lifecycle transitions.
- Current-state field updates.
- Important metadata promotions or corrections.
- Changes to mutable facts where the old value should remain inspectable.

Useful fields:

- `target_kind`: node, relationship, relationship_context, relationship_state, claim, perception.
- `target_id`
- `target_label`
- `target_relationship_type`
- `field_path`
- `previous_value_json`
- `new_value_json`
- `changed_at`
- `changed_by`: user, system.
- `reason`
- `source_ids`
- `extraction_run_ids`
- `metadata`

When the target is a node-like graph record, link it with `HAS_CHANGE_RECORD`. For bare relationships, store the relationship `id` in `target_id` because Neo4j relationships cannot own outgoing relationships.

### Contradiction Modeling

Use `CONTRADICTS` between claims for explicit contradictions after review. Add a richer contradiction record when the contradiction needs review, severity, resolution state, or clarification history.

The future contradiction judge flow should be agent-invoked, not rule-determined. This is documented here so the Wave 2 graph model is compatible with it, but the judge agent itself is not implemented in Wave 2. The graph layer should not try to prove logical contradiction from the whole graph. Future flow:

1. A memory-writing agent proposes a node, relationship, claim, perception, or relationship state.
2. The context builder retrieves nearby graph context before the write, including current state, relevant history, sources, relationship contexts, perceptions, place/time context, and similar entities.
3. The memory-writing agent compares the proposal with that context.
4. If the agent has a grounded doubt, it invokes the contradiction judge tool with the proposal, retrieved context, and a short explanation of the suspected conflict.
5. The judge may navigate the graph further through read-only tools.
6. The judge classifies the situation and recommends a graph action or user clarification.

Example:

```text
New proposal: the dinner with Marco happened in Milan.
Retrieved context: the same event is currently linked to Turin.
Memory-writing agent doubt: possible location conflict for the same event.
Action: invoke contradiction judge.
```

The judge may decide:

- no_conflict: these are different events or different scopes.
- nuance: both facts can be true with better wording.
- temporal_update: the new statement updates an older state.
- contradiction: the facts cannot both be true in the same scope/time.
- needs_clarification: the user should resolve it.

Possible `ContradictionRecord` fields:

- `contradiction_type`: identity, time, location, relationship, contact_detail, affective, metadata, other.
- `severity`: low, medium, high.
- `status`: detected, needs_clarification, resolved, ignored.
- `reason`
- `detected_by`: memory_writer, future_llm_judge, user, system.
- `detected_at`
- `resolved_at`
- `resolution_summary`
- source references

Future judge output should be structured:

- `decision`: no_conflict, nuance, temporal_update, contradiction, needs_clarification.
- `severity`: low, medium, high.
- `reason`
- `graph_action`: allow_write, write_as_disputed, create_contradiction_record, create_relationship_state, ask_user.
- `clarification_question`

Future deterministic code should provide guardrails, not contradiction rulings:

- Build focused graph context before write.
- Validate judge input/output schemas.
- Enforce read-only graph access for judge investigation.
- Enforce tool-call limits.
- Prevent direct graph mutation by the judge outside approved write tools.
- Persist judge decisions when they affect memory.

Do not implement fixed deterministic contradiction rules in the graph wave. In Wave 2, implement only the graph structures and service methods to create/query contradiction records. The future judge flow can write to those structures later.

Wave 2 service/API support should include:

- Create contradiction record.
- Link contradiction record to claims, entities, relationship contexts, or sources.
- Query contradiction records by target, status, severity, and contradiction type.
- Update contradiction record status or resolution summary with a `ChangeRecord`.

### Merge And Split Audit

Add graph-first `MergeRecord` support for entity unification. A merge record is created when the system decides that two or more graph nodes represent the same real-world entity.

Purpose:

- Preserve why a merge happened.
- Keep identity decisions auditable.
- Support debugging wrong merges.
- Prepare for future split/revert workflows.

Useful fields:

- `merged_node_ids`
- `canonical_node_id`
- `reason`
- `merged_at`
- `performed_by`: user, system, future_llm_judge.
- `status`: proposed, applied, reverted.
- source references

Wave 2 should implement actual merge application as a non-destructive graph operation:

- Select one canonical node.
- Create a `MergeRecord`.
- Link the merge record to merged nodes with `MERGED_NODE`.
- Link the merge record to the canonical node with `CANONICAL_NODE`.
- Link merged nodes to the canonical node with `MERGED_INTO`.
- Archive merged nodes instead of deleting them.
- Preserve merged node IDs.
- Copy useful aliases and source references to the canonical node when this does not create conflicts.
- Keep conflicting fields on the merged node or as `ChangeRecord`/metadata rather than overwriting canonical values silently.
- Create `ChangeRecord` entries for lifecycle changes and canonical field changes.

This gives us a real merge operation without making identity history irreversible.

Splits should be supported later. Until split/revert is implemented, risky merges should remain proposed or require user confirmation.

Wave 2 service/API support should include:

- Create proposed merge record.
- Apply merge record.
- Query merge records by canonical node, merged node, and status.
- Retrieve canonical node for a merged node.
- Reject or archive a proposed merge.

### Affective Provenance

Affective memory should separate strong user-stated perception from weaker model or system interpretation.

Strong form:

```json
{
  "description": "The user perceived some traits as oppressive.",
  "source_kind": "user_stated",
  "original_user_words": "I felt his traits as oppressive"
}
```

Weaker forms such as `llm_inferred` or `system_derived` may be stored, but should not be treated as equally strong in retrieval or answers.

Do not ask LLMs to provide numeric affective confidence in v1. Use provenance fields, source links, and user confirmation instead.

### Deferred From Wave 2

Keep these out of the immediate Wave 2 graph implementation unless they become necessary:

- Role separation for graph access.
- Backup/export hardening.
- Richer relational indexes.
- Vector namespace/versioning strategy.
- Telegram clarification behavior.
- Contradiction judge agent or judge invocation flow.
- Hard-coded deterministic contradiction rules.

### Wave 2 Public Interfaces

Add graph service/API support for:

- Create/query relationship states for a relationship context.
- Retrieve current relationship context with optional state history.
- Create/query change records.
- Apply lifecycle transitions with `ChangeRecord` creation.
- Create/query/update contradiction records.
- Create/query/apply merge records.
- Resolve canonical node for a merged node.

These interfaces remain graph-level. They should not include Telegram, LLM judging, speech-to-text, or natural-language ingestion behavior.

## Wave 3: Advanced Graph Capabilities

Wave 3 is the last graph-foundation wave before moving heavier attention to ingestion,
chatting, retrieval, and frontend. The goal is to make the rich graph usable: queryable,
timeline-ready, map-ready, visualization-ready, and ready to produce clean LLM context.

Locked Wave 3 direction:

- Add graph query helper services instead of forcing every caller to compose low-level graph API calls.
- Add timeline-oriented query outputs for memories near a query target.
- Add practical historical inspection, not perfect point-in-time graph reconstruction.
- Add frontend-friendly graph view outputs.
- Add a simple analytics baseline, with deeper analytics deferred.
- Keep stale/expired state support, but do not add proactive stale detection or automatic
  maintenance prompts in this graph wave.
- Add map-ready place and event query helpers without external map enrichment yet.
- Add LLM-friendly graph context packages that include relevant informative fields and avoid noisy metadata.
- Keep vector and embedding writes mostly out of this graph wave unless a minimal interface is needed.
- Add `Animal` as a first-class node type.
- Add a user-perceived social grouping model for family, close friends, colleagues, and other personal circles.

### Graph Query Helpers

Add higher-level read helpers for common memory questions:

- Find memories involving a node.
- Find memories involving a person, place, event, topic, organization, animal, object, or social circle.
- Get entity detail with direct relationships, relationship contexts, perceptions, sources, contradictions, merge status, and change records.
- Get current facts by default and include historical records only when requested.
- Get source evidence for a graph record.
- Get latest known contact details.
- Find possible duplicates through existing merge/canonical data and simple name/alias lookup.
- Find contradictions by target, severity, status, and type.

These helpers should return structured response objects rather than raw Neo4j records.

### Timeline And Memory Stream

Add a normalized `TimelineItem` read model. The timeline should be a
stream of relevant memory-bearing nodes and relationships collected from a query seed.

Example flow:

```text
User asks: "What happened during my last vacation in Greece?"
System retrieves similar or matching graph seeds.
System expands bounded neighbors: events, places, people, sources, perceptions, claims.
System converts memory records into `TimelineItem` objects.
System sorts by inferred or provided memory time.
System passes the timeline package to an LLM for a human-friendly answer.
```

Timeline sorting should prefer:

1. `resolved_start`
2. `valid_from`
3. `source_time`
4. `observed_at`
5. source `received_at`
6. `created_at`

The output should preserve the chosen time basis so downstream answers can distinguish:

- when something happened
- when the user said it
- when the source was created
- when the system learned it

### Historical Inspection

Wave 3 should support practical history views:

- Current record.
- Relationship state history.
- Change records.
- Related claims and perceptions in a time range.
- Contradiction and merge records.

Do not attempt a perfect historical graph snapshot in this wave. The first useful
version is "show me what changed and what was recorded around this period."

### Frontend-Friendly Graph Views

Add saved and generated graph-view outputs for future dashboard work:

- Bounded neighborhood view.
- Entity detail view.
- Timeline view.
- Relationship history view.
- Affective context view.
- Map view input.
- Merge/contradiction review view.

Graph views should include stable display fields:

- node ID and label
- display title
- short description
- lifecycle/privacy/trust markers
- affective summary when present
- temporal summary when present
- relationship type and direction
- metadata only when useful for display or debugging

Archived or merged nodes should be hidden by default, but expandable when the user
asks for history or identity details.

### Analytics Baseline

Add simple graph analytics for personal insight and debugging:

- Most mentioned people, places, topics, organizations, animals, and objects.
- Most connected nodes.
- Nodes with many sources.
- Nodes with unresolved contradictions.
- Nodes with frequent changes.
- Relationship contexts with many state changes.
- Recurring emotional tags.
- Emotionally dense memories.
- Relationship tone changes over time.

This baseline should use simple counts and query helpers. Deeper clustering,
centrality, and embedding-based analytics can come later.

### Stale And Expired Facts

The graph should support stale and expired lifecycle states, but Wave 3 should not
implement proactive stale detection, scheduled maintenance jobs, or automatic
clarification prompts.

Staleness should come from external input:

- The user corrects or updates a fact.
- A new source provides newer information.
- A future external integration reports updated contact, calendar, map, or profile data.
- The user explicitly asks the system to review or clean a category of memories.

Rationale:

- The product exists to preserve memories, not to nag the user into database
  maintenance.
- The user may not know whether old information is still valid.
- Proactive stale prompts can create clarification fatigue.
- Without real usage data, stale thresholds would be arbitrary.

Wave 3 should therefore provide the primitives, not the behavior:

- Query mutable facts and their observed/source times.
- Mark a fact stale, expired, confirmed, or archived through explicit lifecycle tools.
- Preserve the previous value with `ChangeRecord`.
- Return enough context for a future memory-management agent to explain why it is
  suggesting a lifecycle change.

Example flow:

```text
Stored fact: Marco has phone number +39..., observed in 2022.
No automatic process changes it.
Later, the user says: "Marco changed number; the old one is no longer valid."
The system marks the old ContactPoint as expired or stale.
The new ContactPoint is stored as current.
A ChangeRecord preserves the lifecycle transition.
```

Future optional stale review can be added later as an explicit user-invoked or
agent-invoked maintenance task. Example:

```text
User asks: "Review old contact details."
System finds active contact points last observed years ago.
System returns candidates with reasons.
The chatbot asks only if the user chooses to review them.
```

This future feature should be opt-in, explanation-driven, and conservative.

### Map-Ready Queries

Add map-ready query helpers without external map enrichment in Wave 3:

- Places with coordinates.
- Places missing coordinates.
- Events linked to places.
- Memories by city, country, region, or place.
- Timeline items with place references.
- Place clusters and emotionally meaningful places.

The graph should expose enough structured data for a later map dashboard or Google
Maps enrichment service without requiring that service now.

### LLM-Friendly Graph Context Packages

Add read models that prepare graph context for answer generation and future agents.
These packages should be readable, compact, and low-noise.

Principle:

- Provide relevant information needed to answer or reason.
- Exclude raw noisy metadata unless it is directly useful.
- Prefer descriptions, emotional summaries, original user words, time summaries,
  relationship context, provenance summaries, contradictions, and source references.
- Use LLM-facing aliases instead of raw UUIDs.
- Include enough history for the task, but not the entire graph history.

Example package sections:

- target summary
- current facts
- relevant relationships
- relationship context and state history
- perceptions and affective context
- timeline snippets
- source evidence summary
- contradiction or merge notes
- alias map

### Animal Node

Add `Animal` as a first-class node type. Pets and meaningful animals can carry
memories, relationships, locations, events, perceptions, emotional context, and
life history in the same way people and objects can.

Useful properties:

- `name`
- `normalized_name`
- `aliases`
- `species`
- `breed`
- `sex`
- `status`
- `known_since`
- `date_of_birth`
- `date_of_death`
- `owner_hint`
- common temporal, provenance, privacy, lifecycle, metadata, and affective fields

`Animal` should support relationships such as:

- `LIVES_WITH`
- `OWNED_BY` or `CARED_FOR_BY`
- `PARTICIPATED_IN`
- `MENTIONED_IN`
- `HAS_AFFECTIVE_CONTEXT`
- `PERCEPTION_OF`
- `RELATIONSHIP_WITH` through `RelationshipContext`

### Social Circles And User-Perceived Grouping

Support user-perceived social grouping through a dedicated `SocialCircle` node.
This should model personal categories such as family, close friends, colleagues,
university friends, old friends, neighbors, or project circles.

This is not objective taxonomy. It is a subjective memory organization layer.

Useful `SocialCircle` properties:

- `name`
- `normalized_name`
- `circle_type`
- `description`
- `source_kind`
- temporal fields
- common provenance, privacy, lifecycle, metadata, and affective fields

Membership should allow multiple circles per person or animal:

```text
Lorenzo -> MEMBER_OF -> Close friends
Alessandro -> MEMBER_OF -> Colleagues
Brother -> MEMBER_OF -> Family
```

Use relationship properties for simple membership:

- `role`
- `source_kind`
- `valid_from`
- `valid_to`
- `lifecycle_state`
- `source_ids`

Use `RelationshipContext` when the membership itself has emotional weight,
history, contradiction risk, or rich narrative meaning.

Locked naming decision:

- Use `MEMBER_OF` for social circle membership.

## Graph Write Rules

- All writes go through the Network API.
- LLM output creates graph write proposals, not direct graph mutations.
- Every created node should have a stable `id`.
- Model-facing aliases must be resolved to internal UUIDs before writes.
- Every important fact should link to source evidence or include source IDs.
- Updates should preserve old values when history matters.
- Sensitive fields should carry `privacy_level`.
- Low-confidence facts should use `Claim` nodes or lifecycle/trust metadata rather than pretending to be canonical.
- Subjective perceptions should not be written as objective properties on target entities.
- Affective information should mark whether it is user-stated, LLM-inferred, or system-derived.
- Affective memory should not be limited to people. If a place, event, object, topic, organization, source, claim, or relationship carries emotional meaning, preserve that signal explicitly.
- Use direct affective properties for simple relationship tone. Use `RelationshipContext` or `Claim` when a relationship needs history, provenance, contradiction handling, or richer affective description.
- Deletion should be explicit; archival, expiration, or dispute is preferred when preserving memory is useful.

## Query Patterns To Support Early

- Find entity by name or alias.
- Get entity detail with relationships and sources.
- Get event participants and location.
- Get memories involving a person.
- Get memories at a place or in a city.
- Get memories by time range.
- Get latest known contact details.
- Get source evidence for a claim or entity.
- Get perceptions associated with an entity.
- Get relationship context between the user and another entity, or for any important relationship modeled as a memory object.
- Get emotional summaries and original user wording for any memory-bearing node or important relationship.
- Find possible duplicates.
- Find contradictions.
- Build a focused graph neighborhood for visualization.
- Resolve LLM-facing aliases back to graph UUIDs during tool execution.

## Security And Backup

Live graph access:

- Require graph database authentication.
- Use strong generated credentials.
- Keep graph DB private to the backend/container network.
- Use separate read/write and maintenance users when useful.
- Avoid exposing graph admin ports by default.

Graph copies and downloads:

- Export graph, source records, and media references as a package.
- Include manifest with schema version, export timestamp, included stores, checksums, and export tool version.
- Encrypt backup packages before local storage or remote upload.
- Optionally sign the manifest.
- Require authentication for remote download.
- Use short-lived tokens or signed URLs for remote backup downloads.
- Verify manifest and checksums before restore.

## Migration And Versioning

- Track graph schema version.
- Keep versioned Cypher migrations or equivalent migration files.
- Keep relational migrations for operational tables.
- Keep vector schema/version metadata for embedding namespaces.
- Migrations should create constraints and indexes explicitly.
- Breaking schema changes should include backfill steps.
- Prompt/schema versions should be stored on extraction runs.
- Reprocessing old sources should not create duplicate graph facts.

## Risks

- Too many node types too early can slow development.
- Too few typed fields can make querying weak.
- Metadata sprawl can make the graph inconsistent.
- Incorrect merges can corrupt memory identity.
- Direct relationship provenance is limited in Neo4j unless represented through properties or claim nodes.
- Database authentication protects the running graph service, but it does not protect copied database files or exported backups by itself.
- Rich v1 schemas can create false confidence if extraction quality is weak.
- LLMs can over-interpret emotion if user-stated perception and inferred affect are not separated.
- Exposing long opaque UUIDs to LLMs can increase token usage and model copy errors.
- A relational store adds operational complexity, but it prevents the graph from becoming a dumping ground for app runtime state.
- A separate vector store adds one more dependency, but it keeps semantic retrieval portable across local and cloud modes.

## Initial Success Criteria

- Can create and query core entities and relationships.
- Every graph fact links back to source evidence or stores source IDs.
- Can represent uncertain claims.
- Can represent user-stated perceptions and relationship contexts for people, places, events, objects, topics, organizations, sources, claims, and important relationships.
- Can retrieve emotional summaries and original user wording with factual graph context across the whole memory graph.
- Can represent contact details and external references.
- Can preserve old values instead of overwriting important memory history.
- Can query memories by person, place, topic, source, and time.
- Can build a focused graph neighborhood for visualization.
- Can persist operational state in the relational store.
- Can store and retrieve embeddings through the vector store protocol.
- Can map internal UUIDs to LLM-facing aliases and resolve them back safely.
- Graph access requires authentication.
- Local or downloaded graph copies are protected by the backup/export security policy.
