# Interrogation Flow

## Purpose

The interrogation flow lets the user query the digital brain through natural language, structured queries, and graph navigation.

## Query Modes

### Natural Language

The user asks a question in ordinary language. The system converts the question into retrieval actions, graph traversals, and answer generation.

### Structured Query

Advanced users or internal tools can run graph-native or SQL-like queries against the memory graph.

### Visual Navigation

The frontend displays relevant subgraphs and lets the user expand, filter, inspect, and traverse connected entities.

### Timeline View

The frontend displays memories by event time, source time, or ingestion time. This is important for browsing memories without needing to know the exact query.

### Map View

The frontend displays places and place-linked events geographically. This helps the user explore memories by city, venue, trip, or recurring location.

## Graph-RAG Flow

1. User asks a question.
2. System classifies intent: lookup, exploration, summary, comparison, timeline, contradiction check, or graph operation.
3. Semantic retrieval finds relevant sources, entities, claims, and summaries.
4. Graph traversal expands around high-confidence hits, including perception and relationship-context nodes for any relevant memory target.
5. Evidence is gathered and ranked.
6. Affective context such as emotional summaries, original user wording, and user-stated perceptions is included when it helps answer the question.
7. The answer generator produces a grounded response.
8. The response includes uncertainty, missing information, and source references where useful.
9. Contradictions are surfaced when they materially affect the answer.
10. The user can follow up, ask for visualization, or correct the graph.

## Retrieval Strategy

Retrieval should combine:

- Embedding search over sources and entity summaries.
- Semantic text-to-node retrieval that turns a natural language query into likely
  graph seed nodes before graph expansion.
- Exact graph lookup for names, aliases, dates, and places.
- Graph expansion from retrieved entities.
- Expansion through perceptions, affective fields, and relationship contexts.
- Time and location filters.
- Relationship type filters.
- Confidence and provenance filters.

The system should avoid answering from embeddings alone when graph evidence is available.

Semantic text-to-node retrieval is a dedicated retrieval feature, not part of the
graph storage foundation. The graph layer should expose seed-based query helpers;
the retrieval layer decides how natural language maps to those seeds.

## Answer Grounding

Answers should be based on graph facts and evidence, not only model memory.

The system should expose:

- Which entities were used.
- Which relationships were used.
- Which sources support the answer.
- Whether facts are inferred, confirmed, or uncertain.
- Which emotional or perceptual context is user-stated versus inferred.
- Conflicts or missing data.

## Example Questions

- What do I know about Marco Rossi?
- Who was involved in the dinner where we discussed the new project?
- Show me events connected to Milan in 2025.
- Which people are connected to both Capco and my university memories?
- What places in Italy have I mentioned most often?
- Do I have conflicting information about where that meeting happened?
- What happened with Alessandro?
- What emotional memories do I associate with that period?
- Why does that place, object, topic, or project feel important to me?

## Structured Query Requirements

The query layer should support:

- Entity search by type, name, alias, and embedding.
- Relationship traversal by type and depth.
- Affective-context lookup for any memory-bearing node or important relationship.
- Filtering by confidence, source, date, and place.
- Neighborhood extraction for frontend visualization.
- Explain/debug mode for retrieval traces.
- Timeline extraction for chronological visualization.
- Map result extraction for geographic visualization.

## Visualization Handoff

When a natural language query produces graph results, the system should be able to hand the result set to the frontend as:

- Seed entities.
- Expanded relationships.
- Ranking scores.
- Suggested filters.
- Evidence references.
- Layout hints.
- Timeline grouping when time is relevant.
- Geographic grouping when places are relevant.

The frontend should then render a focused graph neighborhood instead of the entire brain.
