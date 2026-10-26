# Task 4.1.2a — assess and upgrade deterministic memory search

**Status: Implemented for review**

## User story

As an application capability, I need one owner-scoped search service that can
retrieve and hydrate graph context through semantic queries, deterministic
filters, or both, so direct callers and AI tools reuse the same behavior.

## What and why

Assess the existing `SemanticMemorySearchService`, `GraphQueryService`, and
their storage collaborators before writing target code. Preserve useful search,
hydration, ranking, and projection behavior, but remove dependencies that make
the reusable service depend on legacy agentic or ingestion orchestration.

Upgrade or reorganize the existing implementation rather than creating a
second competing search engine. Keep vector retrieval, graph hydration, and
model-facing projection as distinct responsibilities.

## Functional boundary

The typed search request must support:

- an optional semantic query;
- optional deterministic object, relationship, known-reference, and temporal
  filters justified by the graph boundary;
- a bounded neighborhood depth from zero through three;
- a bounded result limit.

At least a semantic query or one deterministic filter is required. Owner scope
is a bound backend dependency and is never accepted from model-visible input as
authorization.

The deterministic result retains backend identity only inside the application
boundary. It provides the typed objects, relationships, paths, and relevant
content needed by the tool adapter to produce a model-safe packet.

## Where and acceptance

- Scope-specific models and service protocol under
  `src/product/application/memory_search/`.
- Focused adapter or reorganization of the current graph/vector search
  integrations, with no legacy agentic runtime dependency.
- Tests cover semantic-only, filters-only, combined search, bounded hydration,
  owner scope, empty results, and reuse of the existing retrieval behavior.
- No LLM call, toolbox, agentic state, or user-facing answer is implemented in
  this task.

## Implementation checkpoint

`product.application.memory_search` now owns the target request, filters,
internal hydrated-result models, owner-aware backend protocol, and deterministic
`MemorySearchService`. The service combines ranked semantic and deterministic
seeds once, removes duplicate backend objects, and delegates hydration without
reimplementing vector ranking or graph traversal.

`ExistingMemorySearchBackend` is the integration adapter over the current
`SemanticMemorySearchService` and `GraphService`. It validates canonical graph
labels/types through the graph registry, enforces its bound owner, supports
zero-to-three-degree hydration, applies temporal and relationship refinements,
and returns coherent bounded internal records. Relationship/time filters refine
selected neighborhoods; they cannot identify a graph seed without a semantic
query, property query, node label, or resolved seed ID.

Shared reference allocation is delivered by Task 4.1.2b; model-facing search
projection then uses it in Task 4.1.2c. This service intentionally retains
backend identities only inside its typed application result.
