# Task 4.1.2d — implement `MemoryQueryState`

**Status: Ready for review**

## User story

As a direct caller or parent AI state, I want an agentic memory query to search
iteratively for the context needed to resolve a specific goal and return one
compact grounded result.

## What and why

Implement the query state on `BaseAgenticState` with its own versioned prompt,
scope-specific request/result models, and a toolbox containing at least
`search_memory`.

Before the main LLM call, perform one deterministic semantic search using the
query goal as the default search text and a bounded first-degree hydration.
Render that initial packet into the query prompt. During the main session the
LLM may call `search_memory` again with refined queries, deterministic filters,
or a different bounded depth until it can resolve the goal.

This iterative main tool loop is the state’s reasoning mechanism. Do not add a
separate reasoning or planning stage without a reviewed need.

## Functional contracts

- Input: the query goal; owner scope and selected history remain runtime
  dependencies rather than model arguments.
- Initial context: the deterministic model-facing search packet.
- Output: a structured grounded answer, concise supporting facts, and explicit
  uncertainties or missing information.

The state is read-only, does not ask the user for clarification, and does not
expose graph-write tools. Weak or empty evidence produces an honest bounded
result rather than invented facts.

## Where and acceptance

- State package under `src/product/application/states/memory_query/`, separating
  `models.py` from state behavior.
- Exact-version prompt under `src/product/prompts/templates/memory-query/`.
- Tests cover initial retrieval before the LLM, zero or multiple subsequent
  search calls, structured completion, empty evidence, and no write tools.
