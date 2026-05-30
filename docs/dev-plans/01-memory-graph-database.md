# Memory Graph Database Definition

## Goal

Define the local graph database that stores memories, entities, relationships, claims, sources, profile memories, metadata, provenance, and queryable structure for Graph-RAG.

The graph database is the canonical memory store. It should be rich enough from v1 to preserve provenance, uncertainty, time, lifecycle, privacy, and affective memory, while keeping the number of entity classes controlled.

## Design Stance

- Prefer a rich core schema over many premature node classes.
- Keep source evidence and provenance first-class.
- Use direct relationships for high-confidence graph structure.
- Use `Claim` nodes for uncertain, disputed, temporal, or evidence-heavy facts.
- Use `Perception` and `RelationshipContext` nodes for subjective and emotionally meaningful memory.
- Preserve emotional summaries and original user wording as first-class memory fields when present.
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
- Emotional fields: include `emotional_summary`, `emotional_valence`, `emotional_intensity`, `emotion_tags`, and `original_user_words` where relevant.
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

Most memory nodes should include:

- `id`
- `created_at`
- `updated_at`
- `description`
- `confidence`
- `trust_level`
- `privacy_level`
- `lifecycle_state`
- `metadata`

Affective fields should be available on emotionally meaningful nodes:

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
- `PERCEIVES`: Person to Perception.
- `PERCEPTION_OF`: Perception to target entity.
- `HAS_RELATIONSHIP_CONTEXT`: Person to RelationshipContext.
- `RELATIONSHIP_WITH`: RelationshipContext to target entity.

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
- `source_ids`
- `extraction_run_ids`
- `metadata`

Important Neo4j constraint: relationships cannot have outgoing relationships to evidence nodes. For v1, relationship provenance can be stored through `source_ids`, `extraction_run_ids`, and metadata. When a relationship needs richer evidence, contradiction handling, or temporal nuance, represent the fact as a `Claim` node linked to sources.

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

Vector indexes should be managed in the external vector store rather than Neo4j for v1. Neo4j may still have full-text indexes for graph-native lookup.

## Wave 2: Rich Memory Semantics

- Add temporal fields for event time, valid time, observed time, source time, and ingestion time.
- Support fuzzy time and precision metadata.
- Add lifecycle state transitions: active, confirmed, inferred, disputed, stale, expired, archived, deleted.
- Add contradiction modeling with `CONTRADICTS`.
- Add merge/split audit records.
- Add indexes for names, aliases, time, source IDs, lifecycle state, and privacy level.
- Add role separation for graph access, such as app read/write, read-only, and maintenance users.
- Add backup/export metadata for graph copy creation, including schema version, export timestamp, checksum, and encryption status.
- Add relationship promotion rules: when a generic `RELATED_TO` or metadata value becomes important, migrate it to a typed relationship, property, or claim.
- Add affective extraction review rules for separating user-stated perceptions from LLM-inferred emotional summaries.
- Add richer relational indexes for session lookup, source lookup, provider logs, and audit queries.
- Add vector namespace/versioning strategy for re-embedding when models change.

## Wave 3: Advanced Graph Capabilities

- Graph neighborhood summaries.
- Graph-native embeddings for entities, claims, sources, and neighborhoods.
- Optional graph-native embeddings if Neo4j vector indexes become useful in addition to the external vector store.
- Historical views of entity state over time.
- Automatic stale fact detection.
- Graph analytics: most-mentioned people, places, topics, relationship density, memory clusters.
- Affective graph analytics: recurring emotional tags, relationship tone changes, and emotionally dense memory clusters.
- Saved graph views for frontend visualization.
- Timeline-ready query helpers.
- Map-ready place and event extraction.

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
- Get relationship context between the user and another entity.
- Get emotional summaries and original user wording for a memory.
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
- Can represent user-stated perceptions and relationship contexts.
- Can retrieve emotional summaries and original user wording with factual graph context.
- Can represent contact details and external references.
- Can preserve old values instead of overwriting important memory history.
- Can query memories by person, place, topic, source, and time.
- Can build a focused graph neighborhood for visualization.
- Can persist operational state in the relational store.
- Can store and retrieve embeddings through the vector store protocol.
- Can map internal UUIDs to LLM-facing aliases and resolve them back safely.
- Graph access requires authentication.
- Local or downloaded graph copies are protected by the backup/export security policy.
