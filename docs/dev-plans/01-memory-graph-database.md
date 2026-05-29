# Memory Graph Database Definition

## Goal

Define the local graph database that stores memories, entities, relationships, claims, sources, profile memories, metadata, and provenance.

## Wave 0: Baseline Decisions

- Choose graph database for MVP, likely Neo4j unless implementation reveals a better option.
- Define graph schema v1 with rich fields but controlled node classes.
- Decide where source artifacts live: graph references plus local source/media storage.
- Decide how embeddings are stored: graph-native vector index, external vector store, or deferred.
- Define ID strategy for entities, relationships, sources, claims, and extraction runs.
- Enable graph database authentication from the beginning.
- Keep the graph database reachable only from the backend/container network unless explicitly exposed for local debugging.

## Wave 1: MVP Graph Schema

Implement core node types:

- `Person`
- `Event`
- `Place`
- `Organization`
- `Object`
- `Topic`
- `Source`
- `Claim`
- `ProfileMemory`
- `ContactPoint`
- `ExternalReference`

Implement core relationships:

- `MENTIONED_IN`
- `SUPPORTED_BY`
- `DERIVED_FROM`
- `PARTICIPATED_IN`
- `HAPPENED_AT`
- `ABOUT`
- `RELATED_TO`
- `HAS_CONTACT_POINT`
- `HAS_EXTERNAL_REFERENCE`
- `DESCRIBES_USER`

Add common properties:

- `id`
- `created_at`
- `updated_at`
- `description`
- `confidence`
- `trust_level`
- `privacy_level`
- `lifecycle_state`
- `metadata`

## Wave 2: Rich Memory Semantics

- Add temporal fields for event time, valid time, observed time, source time, and ingestion time.
- Support fuzzy time and precision metadata.
- Add lifecycle state transitions: active, confirmed, inferred, disputed, stale, expired, archived, deleted.
- Add contradiction modeling with `CONTRADICTS`.
- Add merge/split audit records.
- Add indexes for names, aliases, time, source IDs, lifecycle state, and privacy level.
- Add role separation for graph access, such as app read/write, read-only, and maintenance users.
- Add backup/export metadata for graph copy creation, including schema version, export timestamp, checksum, and encryption status.

## Wave 3: Advanced Graph Capabilities

- Graph neighborhood summaries.
- Graph-native embeddings for entities, claims, sources, and neighborhoods.
- Historical views of entity state over time.
- Automatic stale fact detection.
- Graph analytics: most-mentioned people, places, topics, relationship density, memory clusters.

## Risks

- Too many node types too early can slow development.
- Too few typed fields can make querying weak.
- Metadata sprawl can make the graph inconsistent.
- Incorrect merges can corrupt memory identity.
- Database authentication protects the running graph service, but it does not protect copied database files or exported backups by itself.

## Initial Success Criteria

- Can create and query core entities and relationships.
- Every graph fact links back to source evidence.
- Can represent uncertain claims.
- Can represent contact details and external references.
- Can preserve old values instead of overwriting important memory history.
- Graph access requires authentication.
- Local or downloaded graph copies are protected by the backup/export security policy.
