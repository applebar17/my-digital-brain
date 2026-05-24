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

## Graph-RAG Flow

1. User asks a question.
2. System classifies intent: lookup, exploration, summary, comparison, timeline, contradiction check, or graph operation.
3. Semantic retrieval finds relevant sources, entities, claims, and summaries.
4. Graph traversal expands around high-confidence hits.
5. Evidence is gathered and ranked.
6. The answer generator produces a grounded response.
7. The response includes uncertainty, missing information, and source references where useful.
8. The user can follow up, ask for visualization, or correct the graph.

## Retrieval Strategy

Retrieval should combine:

- Embedding search over sources and entity summaries.
- Exact graph lookup for names, aliases, dates, and places.
- Graph expansion from retrieved entities.
- Time and location filters.
- Relationship type filters.
- Confidence and provenance filters.

The system should avoid answering from embeddings alone when graph evidence is available.

## Answer Grounding

Answers should be based on graph facts and evidence, not only model memory.

The system should expose:

- Which entities were used.
- Which relationships were used.
- Which sources support the answer.
- Whether facts are inferred, confirmed, or uncertain.
- Conflicts or missing data.

## Example Questions

- What do I know about Marco Rossi?
- Who was involved in the dinner where we discussed the new project?
- Show me events connected to Milan in 2025.
- Which people are connected to both Capco and my university memories?
- What places in Italy have I mentioned most often?
- Do I have conflicting information about where that meeting happened?

## Structured Query Requirements

The query layer should support:

- Entity search by type, name, alias, and embedding.
- Relationship traversal by type and depth.
- Filtering by confidence, source, date, and place.
- Neighborhood extraction for frontend visualization.
- Explain/debug mode for retrieval traces.

## Visualization Handoff

When a natural language query produces graph results, the system should be able to hand the result set to the frontend as:

- Seed entities.
- Expanded relationships.
- Ranking scores.
- Suggested filters.
- Evidence references.
- Layout hints.

The frontend should then render a focused graph neighborhood instead of the entire brain.
