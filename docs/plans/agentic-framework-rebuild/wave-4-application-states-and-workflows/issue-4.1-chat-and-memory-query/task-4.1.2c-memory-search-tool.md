# Task 4.1.2c — expose reusable `search_memory` tool

**Status: Not started**

## User story

As a configured AI state, I want a typed read-only memory-search tool so I can
request relevant context without receiving database identifiers or depending
on graph-storage implementation details.

## What and why

Register the deterministic search capability as one reusable tool. The handler
binds the authenticated owner scope, search service, and invocation-scoped
reference mapper. It validates the model request, executes deterministic
search/hydration, and projects one bounded model-facing result packet.

The reference mapper is the shared implementation delivered by Task 4.1.2b;
this tool does not create another registry, counter, or UUID-redaction path.

The model-visible request exposes only the accepted semantic query, filters,
neighborhood depth, and limit. Existing local references may be supplied as
filters. The handler resolves them to backend IDs before search and registers
every returned backend object with the same mapper afterward.

## Model-facing result

Return explicit object and relationship models containing coherent local
references, readable labels, summaries or relevant content, and relationship
endpoints expressed through those same references. Do not return UUIDs, vector
IDs, raw vector hits, arbitrary database properties, or an untyped metadata
bag. Repeated searches in one session must reuse the same local reference for
the same backend object.

## Where and acceptance

- Models in a scope-specific `models.py`; handler and toolbox composition in
  separate purpose-named modules under `product.application.tools`.
- The registered function is named `search_memory` and can be included in any
  explicitly configured toolbox.
- Validation and backend failures become normal tool error outputs so the
  invoking LLM can adjust its next call.
- Tests cover schema generation, reference translation, coherent repeated
  results, bounded packets, and absence of backend IDs.
