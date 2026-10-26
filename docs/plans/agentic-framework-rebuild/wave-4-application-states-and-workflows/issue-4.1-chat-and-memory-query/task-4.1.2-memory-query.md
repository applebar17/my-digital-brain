# Task 4.1.2 — implement memory-query state

**Status: Planned — split into four reviewed delivery tasks**

## Delivery sequence

This task is the index for five independently reviewable changes. Detailed
behavior remains owned by the canonical
[memory-query state](../../../../ai-engineering/application-states/memory-query-state.md).

1. [Task 4.1.2a — assess and upgrade deterministic memory search](task-4.1.2a-memory-search-service.md)
2. [Task 4.1.2b — implement shared model-reference context](task-4.1.2b-reference-context.md)
3. [Task 4.1.2c — expose reusable `search_memory` tool](task-4.1.2c-memory-search-tool.md)
4. [Task 4.1.2d — implement `MemoryQueryState`](task-4.1.2d-memory-query-state.md)
5. [Task 4.1.2e — compose memory query with conversation entry](task-4.1.2e-memory-query-composition.md)

The fifth task is application composition, not a new `BaseWorkflow`. The
conversation state invokes the query state through a registered agentic tool;
the query state may itself use the deterministic search tool through its normal
provider tool loop.
