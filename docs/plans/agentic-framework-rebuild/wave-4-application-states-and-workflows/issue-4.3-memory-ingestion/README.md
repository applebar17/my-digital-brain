# Issue 4.3 — memory-ingestion states and workflow

**Status: Not started**

Rebuild ingestion as concrete states connected by the accepted deterministic
workflow. Each step receives only the source, owner, evidence, and current
functional reference context it needs; writes happen through typed tools and
deterministic graph services.

## Tasks

- [Task 4.3.1 — define ingestion request and reasoning context](task-4.3.1-ingestion-entry-and-reasoning.md)
- [Task 4.3.2 — resolve and create nodes with coherent references](task-4.3.2-node-resolution-and-write.md)
- [Task 4.3.3 — create memory/context objects after their targets](task-4.3.3-memory-context-write.md)
- [Task 4.3.4 — write relationships from resolved endpoints](task-4.3.4-relationship-write.md)
- [Task 4.3.5 — compose the deterministic ingestion workflow](task-4.3.5-ingestion-workflow.md)

## Dependencies

- [Ingestion flow](../../../../flows/ingestion.md)
- [Ingestion state specifications](../../../../ai-engineering/application-states/ingestion/README.md)
- [Reference-context and owner projection](../../../../ai-engineering/context-and-prompts/reference-context-and-owner-projection.md)
- Issues 3.1, 3.2, and 4.2 where a clarification handoff is required.

## Functional communication DTOs

The workflow begins with source content, owner identity/context, and relevant
conversation/channel context. Reasoning and planning use that context to
produce typed artifacts. Node work receives source evidence and the current
reference inventory, returning resolved/created local refs. Memory and context
work uses those refs to create linked objects. Relationship work receives
resolved endpoint refs plus relationship evidence. The final ingestion result
returns created/updated functional outcomes and a concise summary to the
invoker; database UUIDs remain backend-only.
