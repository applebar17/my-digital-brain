# Vector retrieval and indexing

## Purpose

The vector store is a derived semantic index for the canonical memory graph. It
helps find relevant graph targets, but it never owns memory truth or supplies a
final answer without graph hydration.

## Index contract

The backend builds deterministic, low-noise embedding documents from persisted
graph records. It does not embed raw database payloads or ask an LLM to invent
index text. Every vector record has one primary graph target and may identify
related graph targets and sources required for later hydration.

The operational vector record tracks the collection, embedding scope, primary
and related targets, source references, provider/model, text-builder version,
document checksum, lifecycle state, and timestamps. `builder_version` together
with `document_checksum` determines whether an existing vector document is
current.

Do not index raw UUIDs, backend metadata, provider payloads, prompts, tool
traces, or empty name-only records. Index meaningful source-backed memory,
descriptions, claims, perceptions, relationship context, profile context, and
substantive `MemoryLog` records when their rendered text is useful for recall.

## Write-time behavior

Graph persistence completes before vectorization. A successful graph write is
not reverted because a derived index update failed. The vectorization service
records compact diagnostics and can re-index from persisted graph truth.

It refreshes a document when its informative content, related context, or
lifecycle visibility changes; it skips unchanged documents with the same
builder version and checksum. Archiving, deletion, and canonical identity
changes update or deactivate the associated vector records.

## Retrieval behavior

```text
user question
  -> query embedding
  -> vector hits as candidate pointers
  -> hydrate primary and related graph targets
  -> resolve canonical identity and apply visibility/lifecycle filters
  -> bounded graph and evidence expansion
  -> low-noise retrieval context for answer or UI
```

Ranking may combine semantic similarity with graph proximity, time, lifecycle,
privacy/trust, and available source evidence. Keep the applied ranking factors
observable in developer diagnostics, without exposing raw vector payloads or
backend IDs to normal users.

`MemoryLog` hits hydrate their host, involved targets, and relevant context.
The normal graph workspace renders hydrated domain objects; logs appear in a
timeline or detail view rather than as default graph nodes.

## Boundaries

- The vector provider is accessed through the provider-neutral AI boundary.
- The vector store is replaceable; Chroma is the local implementation and a
  cloud service may be selected behind the same protocol.
- Exact/property graph search and semantic search are complementary. A hybrid
  retrieval result combines their hydrated graph targets, not raw result sets.
- Query answers are grounded in hydrated graph and source evidence, never in
  vector text alone.

## Related documentation

- [Interrogation flow](../flows/interrogation.md)
- [Graph model](graph-model.md)
- [MemoryLog model](memory-log-model.md)
- [Provider integration boundary](../ai-engineering/providers/provider-integration-boundary.md)
