# Issue 4.1 — conversation entry and memory query

**Status: Not started**

Prepare the durable conversation/history boundary, then implement the root chat
agent and the composite memory-query capability. The query state performs
deterministic retrieval/context assembly, then uses its own agentic
conversation; it can be invoked directly or as a child tool.
The root state's `ingest_memory` tool is bound when the concrete ingestion
workflow is delivered in Issue 4.3; no placeholder workflow handler is needed.

## Tasks

- [Task 4.1.0 — prepare durable conversation and history projections](task-4.1.0-conversation-persistence-and-history-projection.md)
- [Task 4.1.1 — implement conversation-entry state](task-4.1.1-conversation-entry.md)
- [Task 4.1.2 — implement memory-query state](task-4.1.2-memory-query.md)

## Dependencies

- [Conversation-entry specification](../../../../ai-engineering/application-states/conversation-entry-state.md)
- [Memory-query specification](../../../../ai-engineering/application-states/memory-query-state.md)
- Wave 2 generic framework. Read/retrieval capabilities and tools are defined
  only if the reviewed state contracts require them.

## Functional communication DTOs

The application entrypoint loads owner-scoped durable conversation entries and
builds separate frontend and model-history projections. Completed
question/answer interactions are readable frontend items and ordered model
messages; raw tool transcripts remain state-local. The entry state receives the
selected model projection and current user text, and may invoke
`MemoryQueryState` with a question and the context selected for that child. The
query result returns a readable, grounded answer/context packet and uncertainty,
not storage IDs. The entry state produces the final user-facing response.
