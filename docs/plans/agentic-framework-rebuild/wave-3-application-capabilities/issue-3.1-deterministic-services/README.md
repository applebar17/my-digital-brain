# Issue 3.1 — migrate deterministic services required by the MVP

**Status: Deferred until an agreed state requires a capability from this issue**

This is a just-in-time capability backlog, not a phase to complete before state
design. For each candidate capability, first reference the state task that needs
it; define its DTO and service boundary there, then implement only the required
behavior under `product`. Keep service behavior independent of prompts and the
agentic runtime.

## Tasks

- [Task 3.1.1 — migrate graph and owner services used by states](task-3.1.1-graph-owner-services.md)
- [Task 3.1.2 — migrate retrieval and context preparation services](task-3.1.2-retrieval-services.md)
- [Task 3.1.3 — preserve the existing human-interaction persistence boundary](task-3.1.3-interaction-persistence.md)

The backend-owned deadline and answer/timeout behavior for tools that request
user input is specified once in the [user-interaction tool contract](../../../../ai-engineering/application-states/user-interaction-tools.md).

## Dependencies

- [System architecture](../../../../architecture/system-architecture.md)
- [State and tool taxonomy](../../../../ai-engineering/application-states/state-and-tool-taxonomy.md)
- Relevant graph, vector, and clarification contracts from the Wave 0 census.

## Candidate capability contracts (non-binding)

Possible deterministic capabilities may receive typed requests such as owner-scoped node
search, graph-context lookup, graph mutation, and interaction answer/resume.
They return found domain objects/context, explicit write outcomes, or a
validated human answer. They do not receive provider transcripts or tool-call
IDs. These examples are not a commitment to implement all of them; a state
review establishes the actual contract when needed.
