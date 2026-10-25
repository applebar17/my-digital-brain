# Task 3.1.2 — migrate retrieval and context preparation services

**Status: Candidate capability — activate only when a reviewed state requires it**

## User story

As a memory-query or ingestion state, I want deterministic retrieval to return
a grounded, owner-scoped context packet, so the model reasons over current
application data instead of inventing identifiers or hidden database state.

## What and why

When a reviewed state requires retrieval/hydration, define its functional
service contract within that state slice and adapt only the needed functions.
Keep deterministic retrieval separate from the LLM state interpreting its
result. This is not an independent migration of all retrieval code.

## Where

- `src/product/retrieval/` or the retained vector/graph service modules under
  `product`.
- Relevant query and ingestion context tests.

## Functional communication DTOs

Input: owner-scoped question/search criteria and optional local seed reference.
Output: ranked candidate/context packet with readable names, evidence, and
uncertainty. The packet may contain local model refs; raw backend identifiers
remain behind the application mapping boundary.

## Dependencies and acceptance

- Depends on Task 3.1.1 where graph hydration is required.
- Deterministic retrieval can be called independently of any agentic state.
- Empty/no-match outcomes are explicit and usable by the state.
- No second LLM client or duplicate semantic search logic is introduced.
