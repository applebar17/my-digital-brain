# Task 4.1.2 — implement memory-query state

**Status: Not started**

## User story

As the conversation-entry state or another caller, I want a memory query to
retrieve relevant owner-scoped context and return a grounded result, so the
invoker can use it without inheriting the query state's internal transcript.

## What and why

Implement deterministic retrieval/hydration followed by the configured
LLM-only or explicitly tool-enabled query state. Keep retrieval separate from
the LLM interpretation and allow direct or child-tool invocation.

## Where

- `src/product/application/states/memory_query.py`.
- `product.application.tools` and deterministic retrieval services.

## Functional communication DTOs

Input: question, owner, selected history/context, optional seed reference.
Preparation output: retrieved records, readable local refs, evidence, and
uncertainties. State result: concise grounded answer plus any useful context
packet the caller contract requests. Backend IDs are not answer content.

## Dependencies and acceptance

- Depends on Task 3.1.2 and the typed read toolbox.
- No-match and weak-evidence cases are explicit to the model.
- Direct invocation and `query_memory` child-tool invocation share the same
  state semantics; the parent receives one compact result.
