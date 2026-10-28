# Issue 4.3 — memory-ingestion state slices and workflow

**Status: In progress — complete through Task 4.3.1**

After the state census in [Issue 4.0](../issue-4.0-first-workflow-and-state-census/README.md),
implement the confirmed memory-ingestion agentic states one at a time in their
agreed execution order. Each state receives only the input, owner, and
functional reference context it needs. Its DTOs, deterministic dependencies,
toolbox, and function mappings are defined as part of that state slice, not
preselected in a separate capability phase.

The concrete `MemoryIngestionWorkflow` inherits the preparatory issue's
`BaseWorkflow`. Its annotated `ingest_memory` method is registered as the
chat-facing tool handler. The assembled step declarations drive both execution
and the local inspector's composition view.

## Tasks

- [Task 4.3.0a — implement invocation context and inherited child history](task-4.3.0a-invocation-context-and-history-inheritance.md)
- [Task 4.3.0b — align existing child states with inherited history](task-4.3.0b-align-existing-child-history.md)
- [Task 4.3.1 — define ingestion request and reasoning context](task-4.3.1-ingestion-entry-and-reasoning.md)
- [Task 4.3.2 — define the node-candidate state](task-4.3.2-node-candidate.md)
- [Task 4.3.3 — resolve and create nodes with coherent references](task-4.3.3-node-resolution-and-write.md)
- [Task 4.3.4 — create memory/context objects after their targets](task-4.3.4-memory-context-write.md)
- [Task 4.3.5 — write relationships from resolved endpoints](task-4.3.5-relationship-write.md)
- [Task 4.3.6 — compose the deterministic ingestion workflow](task-4.3.6-ingestion-workflow.md)

Tasks 4.3.0a–4.3.0b establish and apply framework-level history inheritance
before ingestion code is added. Tasks 4.3.1–4.3.2 then define the two read-only
interpretation states primarily through input/output contracts, prompts,
toolbox configuration, and workflow wiring. Wire each completed state into the
workflow as it is delivered; Task 4.3.6 verifies the complete sequence rather
than deferring all composition until the end.

## Dependencies

- [Ingestion flow](../../../../flows/ingestion.md)
- [Ingestion state specifications](../../../../ai-engineering/application-states/ingestion/README.md)
- [Reference-context and owner projection](../../../../ai-engineering/context-and-prompts/reference-context-and-owner-projection.md)
- [Workflow architecture map](../../../../architecture/memory-ingestion-workflow-map.md)
- [Local workflow inspector](../issue-4-prep-workflow-inspector/README.md)
- Wave 2 generic framework contracts.
- Wave 3 capabilities only when a state task identifies a concrete need.
- Clarification state/tool work only if the state census confirms that handoff.

## Functional communication DTOs

The chatbot's `ingest_memory` tool accepts only optional ingestion guidance. It
does not ask the conversation model to regenerate or copy the memory content.
The framework supplies the invoking state history to the bound workflow, and
the workflow's states inherit that selected projection. The application binds
owner and service dependencies when composing the workflow tool; none are
model-supplied arguments.
As each state is reviewed, define its purpose and input/output first, then its
internal DTOs/artifacts, prompt/history/context, deterministic functions, any
model-visible tools and function mappings, and the next handoff. Local
references remain model-facing handles; backend UUIDs remain behind the mapper.
The typed workflow result returns as one matched tool output to the
conversation-entry state, which owns the final user-facing response.
