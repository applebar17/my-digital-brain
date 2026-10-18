# Issue 4.4 — other MVP application states

**Status: Not started**

Migrate the remaining state purposes from the accepted state taxonomy only to
the extent included in the agreed MVP. Each state remains a distinct concrete
class with its own functional request/result contract; shared runtime/tool
behavior stays in Wave 2.

## Tasks

- [Task 4.4.1 — define remaining state scope and typed handoffs](task-4.4.1-remaining-state-scope.md)

## Candidate states from the current application map

Memory creation, graph update, contradiction review, memory-log extraction, and
profile duplication. Their migration is not automatic: retain only capabilities
needed for the agreed MVP and document deferrals rather than building speculative
states.

## Dependencies

- [State and tool taxonomy](../../../../ai-engineering/application-states/state-and-tool-taxonomy.md)
- Issues 2.3 and 3.2.

## Functional communication DTOs

Each retained state receives its own purpose-specific input context and returns
the functional artifact expected by its caller (for example, a graph-update
decision or contradiction assessment). No shared generic `Any` packet is
introduced merely to make unrelated state outputs look alike.
