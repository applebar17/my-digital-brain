# Graph-RAG And Vector Retrieval Implementation Plan

## Summary

Implement semantic retrieval as a graph-grounded RAG layer. Neo4j remains the
source of truth for memories, relationships, lifecycle, provenance, temporal
state, affective context, contradictions, and merges. Chroma is a semantic
index that points back to Neo4j records.

Locked architecture:

- Graph writes create authoritative nodes and relationships in Neo4j.
- Vector writes create semantic lookup records in Chroma.
- Chroma never owns memory truth. It only returns semantically similar vector
  records with metadata references back to Neo4j.
- RAG answers must be grounded through Neo4j hydration and graph expansion, not
  from vector hits alone.
- Embedding text must be informative and low-noise. Raw UUIDs, raw metadata,
  graph payloads, provider traces, and backend-only fields must not be embedded.
- Embedding payloads are structured by node type and relationship context, not
  generated from arbitrary property dumps.
- A single embedding document may point to one primary graph target and may also
  reference multiple related graph nodes when the embedded memory logically
  spans them.
- Wave 1 uses one Chroma collection first: `memory_documents`.
- Every vector record has exactly one `primary_target_id` and may have multiple
  `related_target_ids`.
- Embedding documents are deterministic backend-built texts for now, not
  LLM-generated summaries.
- Vector freshness is determined through `builder_version` plus
  `document_checksum`.
- Wave 1 builds the vector record and text-builder foundation only. Automatic
  ingestion-time embedding starts in Wave 2.

## Core Flow

### Ingestion-Time Vectorization

1. A source text or transcript is ingested.
2. The ingestion pipeline creates a validated `GraphWritePlan`.
3. The graph executor writes nodes and relationships to Neo4j.
4. A vectorization service receives the executed write result.
5. The vectorization service builds typed embedding documents from the created
   or updated graph records.
6. The embedding provider creates embeddings for those documents.
7. Chroma stores the vectors.
8. The relational operational store records `vector_records` linking each vector
   to its graph targets, source refs, embedding model, text-builder version, and
   lifecycle state.

### Query-Time Retrieval

1. The user asks a natural language memory question.
2. The retrieval layer embeds the query.
3. Chroma returns semantically similar vector records.
4. Backend code hydrates primary and related graph targets from Neo4j.
5. Backend code expands graph neighborhoods around the best targets.
6. Backend code applies lifecycle, privacy, trust, merge/canonical, time, and
   source filters.
7. Backend code builds a low-noise `GraphContextPackage`.
8. The answer generator uses the graph-grounded package to answer.

## What Gets Embedded

The vector layer should embed memory-bearing summaries, not every graph record
or every graph property.

### `Claim`

Embed:

- `text`
- `claim_type`
- relevant time summary
- source/evidence summary when concise

Example embedding document:

```text
Claim: Alessandro and I had a great relationship during teenage years.
Time: teenage years.
Evidence: user-stated memory.
```

Primary graph target:

- the `Claim` node

Related graph targets:

- mentioned `Person`, `Event`, `Place`, `RelationshipContext`, or `Source`
  nodes when linked.

### `Event`

Embed:

- `title`
- `description`
- participants summary
- place summary
- temporal summary
- affective summary when present

Example:

```text
Event: Dinner with Marco at Pizzeria Napoli in Milan.
Time: yesterday.
Participants: Marco.
Place: Pizzeria Napoli, Milan.
```

Primary target:

- the `Event` node

Related targets:

- participant `Person` nodes
- `Place` nodes
- supporting `Source` nodes

### `Perception`

Embed:

- `description`
- `emotional_summary`
- `original_user_words`
- perception target title and label
- whether the perception is user-stated or inferred

Example:

```text
Perception about Alessandro: the user felt his personality was oppressive.
Emotional context: care mixed with distance and discomfort.
Original user wording: "his personality always felt oppressive to me".
```

Primary target:

- the `Perception` node

Related targets:

- the perceived target node, such as `Person`, `Place`, `Object`, `Topic`,
  `Organization`, `Animal`, or `Event`
- relevant `Source` nodes

### `RelationshipContext`

Embed:

- current `description`
- `relationship_type`
- `status`
- `closeness`
- affective fields
- compact relationship-state history
- participants or target nodes

Example:

```text
Relationship with Alessandro: close friendship during teenage years, now low
contact. The user still cares about him but feels distance and remembers
oppressive personality traits.
```

Primary target:

- the `RelationshipContext` node

Related targets:

- both endpoint nodes when available
- `RelationshipState` nodes that explain state history
- relevant `Perception`, `Claim`, `Event`, and `Source` nodes

### `RelationshipState`

Usually do not embed every state as a standalone document unless the state is
substantive. Prefer rolling meaningful state history into the parent
`RelationshipContext` embedding document.

Embed standalone only when:

- it contains a materially different period;
- it has rich affective or temporal information;
- users are likely to search for that state independently.

### `ProfileMemory`

Embed:

- `profile_key`
- `category`
- `value`
- stability or visibility only when informative

Example:

```text
Profile memory: the user prefers quiet restaurants and low-noise environments.
```

Primary target:

- the `ProfileMemory` node

### `Person`

Embed `Person` nodes when they have meaningful descriptive text. Do not embed
bare names.

Embed:

- `display_name`
- `aliases` when useful
- `description`
- `emotional_summary`
- `original_user_words` when present
- compact current relationship/social context when available

Example:

```text
Person: Alessandro.
Description: teenage friend, now low contact.
Emotional context: care, distance, and remembered oppressive personality traits.
```

Primary target:

- the `Person` node

Related targets:

- important `RelationshipContext`, `Perception`, `Claim`, `Event`, and `Source`
  nodes when linked.

### `Place`

Embed `Place` nodes when they carry meaningful description, emotional context,
or recurring memory context. Do not embed bare geographic names only.

Embed:

- `name`
- `address`, `city`, `region`, `country` when informative
- `description`
- `emotional_summary`
- relevant recurring/event context when available

Example:

```text
Place: Pizzeria Napoli, Milan.
Description: recurring dinner place connected to memories with Marco.
```

Primary target:

- the `Place` node

Related targets:

- linked `Event`, `Person`, `Source`, and `Perception` nodes when useful.

### `SocialCircle`

Embed `SocialCircle` nodes when they describe a meaningful user-perceived group
or social class. Do not embed empty category labels.

Embed:

- `name`
- `circle_type`
- `description`
- `emotional_summary`
- member summary when concise

Example:

```text
Social circle: close friends.
Description: people the user perceives as emotionally close and trusted.
Members mentioned: Lorenzo, Marco.
```

Primary target:

- the `SocialCircle` node

Related targets:

- member `Person` nodes and relevant `RelationshipContext` nodes.

### `Source`

Do not embed entire raw source payloads by default.

Embed source snippets only when:

- the source contains a compact memory-bearing text span;
- it is useful for recall independent of extracted nodes;
- the snippet can be linked to graph targets and evidence refs.

## What Does Not Get Embedded

- Raw UUIDs.
- LLM-facing aliases except inside transient retrieval packages.
- Raw metadata dicts.
- Full graph node or relationship JSON.
- Provider request/response payloads.
- Logs, traces, tool calls, or prompt bodies.
- Embeddings themselves.
- Empty or label-only nodes such as `Person(name="Marco")` unless they have a
  meaningful description or profile summary.

## Multi-Target Embedding Records

Some semantic memories naturally span multiple graph records. The vector record
should support:

- `vector_id`
- `collection`
- `primary_target_id`
- `primary_target_label`
- `related_target_ids`
- `source_ids`
- `relationship_ids` when the text summarizes important relationships
- `embedding_scope`
- `embedding_model`
- `builder_version`
- `document_checksum`
- `lifecycle_state`
- timestamps

Example:

```json
{
  "vector_id": "vec_relationship_context_000001",
  "collection": "memory_documents",
  "embedding_scope": "relationship_context_summary",
  "primary_target_id": "relationship-context-uuid",
  "primary_target_label": "RelationshipContext",
  "related_target_ids": ["person-alessandro-uuid", "perception-uuid", "source-uuid"],
  "source_ids": ["source-uuid"],
  "embedding_model": "text-embedding-3-small",
  "builder_version": "relationship_context_summary.v1",
  "document_checksum": "sha256:...",
  "lifecycle_state": "active",
  "document": "Relationship with Alessandro: close friendship during teenage years..."
}
```

This lets a similarity hit hydrate the relationship context first, while still
pulling connected people, perceptions, states, events, and sources into graph
retrieval.

## Node Embedding Updates

Embeddings must be refreshed when informative text changes.

Trigger refresh when these fields change:

- `description`
- `text`
- `title`
- `display_name` only when paired with richer context
- `name` only when paired with richer context
- `emotional_summary`
- `original_user_words`
- `relationship_type`
- `status`
- `closeness`
- temporal fields that materially affect the embedded summary
- source/evidence summary fields

Trigger refresh after these operations:

- new memory ingestion write;
- relationship state made current;
- perception update;
- claim update;
- lifecycle transition to archived/stale/confirmed when it should affect
  retrieval visibility;
- merge application, so vector hits resolve to canonical graph identity.

Implementation should use deterministic text-builder versions. If a builder
changes, vector records can be re-indexed by `builder_version`.

## Similarity Retrieval And Graph Hydration

Similarity search returns vector hits, not graph truth.

Retrieval pipeline:

```text
User query
  -> embed query
  -> Chroma similarity search
  -> vector hits
  -> hydrate primary_target_id from Neo4j
  -> hydrate related_target_ids from Neo4j
  -> resolve canonical nodes through MERGED_INTO
  -> expand graph neighborhood
  -> collect evidence, timeline, affective context, contradictions
  -> build GraphContextPackage
  -> answer generation
```

Example query:

```text
I cannot remember what happened with Alessandro.
```

Potential vector hits:

- `RelationshipContext`: close teenage friendship, now low contact.
- `Perception`: oppressive personality traits.
- `Claim`: great relationship during teenage years.
- `Event`: saw Alessandro again.

Backend then hydrates:

- `Person Alessandro`
- connected `RelationshipContext`
- current and historical `RelationshipState`
- `Perception`
- `Claim`
- relevant `Source` records

The answer generator receives the graph-grounded context, not the raw Chroma
documents alone.

## Ranking Policy

Initial ranking should combine:

- vector distance;
- graph proximity to the query target, when a target exists;
- lifecycle state;
- trust/privacy filters;
- source/evidence presence;
- temporal relevance when the question asks about a period;
- affective relevance when the question asks emotional or perceptual questions.

Do not overfit ranking in the first implementation. Keep the scoring transparent
and easy to debug.

## Public Interfaces

### Backend Services

- `EmbeddingTextBuilder`
  - builds typed embedding documents from graph records.
- `GraphVectorizationService`
  - vectorizes executed graph writes and updates vector records.
- `SemanticMemorySearchService`
  - embeds user queries, searches Chroma, hydrates graph targets, and returns
    graph-grounded retrieval packages.
- `VectorRecordStore`
  - stores vector IDs, graph targets, source refs, embedding model, collection,
    builder version, lifecycle state, and timestamps in the relational DB.

### API Routes

Add routes only after services are in place:

- `POST /graph/vectorize/{target_id}`
- `POST /graph/vectorize/reindex`
- `GET /graph/search/semantic`
- `GET /graph/search/hybrid`

The frontend graph workspace can later use hybrid search as the default search
mode and expose exact/property search as a secondary mode.

## Implementation Waves

### Wave 1: Vector Record Foundation

- Add vector record store methods over existing relational `vector_records`.
- Add embedding text-builder contracts and typed builders per target label.
- Add tests proving each node type produces low-noise embedding text.
- Add deterministic text-builder versioning.
- Use one Chroma collection name: `memory_documents`.
- Lock vector record fields: `vector_id`, `collection`, `embedding_scope`,
  `primary_target_id`, `primary_target_label`, `related_target_ids`,
  `source_ids`, `embedding_model`, `builder_version`, `document_checksum`,
  `lifecycle_state`, and timestamps.
- Require exactly one primary target per embedding document.
- Support multiple related targets per embedding document.
- Include deterministic builders for `Claim`, `Event`, `Perception`,
  `RelationshipContext`, `ProfileMemory`, `Person`, `Place`, and
  `SocialCircle`.
- For `Person`, `Place`, and `SocialCircle`, embed only when meaningful
  `description`, affective context, or contextual summary text exists. Bare
  names or labels are skipped.
- Do not change chat answer generation yet.

### Wave 2: Ingestion-Time Vectorization

- Wire vectorization after successful graph writes.
- Embed `Claim`, `Event`, `Perception`, `RelationshipContext`, substantive
  `RelationshipState`, and `ProfileMemory`.
- Upsert embeddings into Chroma.
- Persist vector record links.
- Add update/delete behavior for archived or replaced vector records.
- Hydrate graph records from Neo4j after write execution before building
  embedding documents. Do not vectorize pre-write candidate payloads.
- Treat vectorization as a post-write retrieval-indexing step. If vectorization
  fails, the graph write remains successful and the ingestion result records
  compact diagnostics.
- Skip unchanged vector documents when `builder_version` and
  `document_checksum` match the existing vector record.
- Archive and delete vector-store entries when a target is archived/deleted or
  when a previously embeddable target no longer has meaningful embedding text.
- Keep Chroma metadata primitive and compact. Store rich graph context in Neo4j
  and hydrate it during retrieval.

### Wave 3: Semantic And Hybrid Retrieval

- Add query embedding.
- Search Chroma.
- Hydrate primary and related Neo4j targets.
- Resolve canonical identities.
- Expand graph neighborhoods.
- Return low-noise retrieval packages for answer generation and graph UI.
- Add debug traces that explain vector hits, graph hydration, and ranking.

### Wave 4: Answer And UI Integration

- Use semantic/hybrid retrieval in `query_memory_context`.
- Let graph workspace switch between property search, semantic search, and
  hybrid search.
- Render retrieval traces in a developer/debug panel.
- Keep final answers grounded in graph evidence.

## Test Plan

- Unit tests:
  - embedding text builders include informative fields and exclude noisy fields;
  - each supported node type has an explicit builder or an explicit skip policy;
  - multi-target vector records preserve primary and related target IDs;
  - vector record store persists model, collection, source refs, and builder
    version.

- Integration tests:
  - successful ingestion creates graph records and vector records;
  - vector records point back to existing Neo4j IDs;
  - updating a relationship state refreshes relevant embeddings;
  - archiving a node hides or deactivates its vector records;
  - semantic search hydrates graph targets and expands neighborhoods.

- Retrieval tests:
  - query about a person retrieves relationship contexts and perceptions;
  - emotional query retrieves affective memories;
  - time-bounded query respects graph temporal fields after vector retrieval;
  - merged nodes resolve to canonical identity;
  - answers are not generated from Chroma hits alone.

## Assumptions

- Chroma remains the first local vector implementation.
- Azure vector search remains a protocol-level future option unless selected
  explicitly.
- Neo4j remains the canonical memory store.
- Embedding generation uses the provider-neutral AI package.
- Embedding documents are deterministic backend outputs, not LLM-authored free
  text unless a future summarization service is explicitly introduced.
