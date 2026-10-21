# Issue 2.2 — shared agentic history session

**Status: In progress**

Implement one session object that shares selected master-history context while
giving each state invocation its own provider-valid local transcript. It links
nested state runs and explicit continuation without becoming a chat database
or an orchestration engine.

## Tasks

- [Task 2.2.1 — implement shared and state-local history](task-2.2.1-history-lifecycle.md)
- [Task 2.2.2 — support paused state continuation](task-2.2.2-paused-continuation.md)

## Dependencies

- [Agentic history-session specification](../../../../ai-engineering/runtime/agentic-history-session.md)
- [Tool-calling protocol](../../../../ai-engineering/runtime/tool-calling-protocol.md)

## Functional communication DTOs

The session tracks a master-history view and each invocation's `StateHistory`
(state identity, run identity, parent linkage, selected history revision, local
transcript reference). A paused continuation carries the open interaction and
the provider transcript needed to resume; durable chat records remain owned by
the application storage boundary.
