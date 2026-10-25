# Issue 4.1 — conversation entry and memory query

**Status: Not started**

Implement the root chat agent and the composite memory-query capability. The
query state performs deterministic retrieval/context assembly, then uses its
own agentic conversation; it can be invoked directly or as a child tool.

## Tasks

- [Task 4.1.1 — implement conversation-entry state](task-4.1.1-conversation-entry.md)
- [Task 4.1.2 — implement memory-query state](task-4.1.2-memory-query.md)

## Dependencies

- [Conversation-entry specification](../../../../ai-engineering/application-states/conversation-entry-state.md)
- [Memory-query specification](../../../../ai-engineering/application-states/memory-query-state.md)
- Wave 2 generic framework. Read/retrieval capabilities and tools are defined
  only if the reviewed state contracts require them.

## Functional communication DTOs

Chat input provides user text, owner context, selected conversation history,
and channel context. The entry state may invoke `MemoryQueryState` with a
question and owner/history context. The query result returns a readable,
evidence-grounded answer/context packet and uncertainty, not storage IDs. The
entry state produces the final user-facing response.
