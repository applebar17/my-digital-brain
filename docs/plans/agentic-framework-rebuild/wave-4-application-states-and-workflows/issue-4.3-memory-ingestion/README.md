# Issue 4.3 — memory-ingestion state slices and workflow

**Status: Not started**

After the state census in [Issue 4.0](../issue-4.0-first-workflow-and-state-census/README.md),
implement the confirmed memory-ingestion agentic states one at a time in their
agreed execution order. Each state receives only the source, owner, evidence,
and functional reference context it needs. Its DTOs, deterministic dependencies,
toolbox, and function mappings are defined as part of that state slice, not
preselected in a separate capability phase.

The concrete `MemoryIngestionWorkflow` inherits the preparatory issue's
`BaseWorkflow`. Its annotated `ingest_memory` method is registered as the
chat-facing tool handler. The assembled step declarations drive both execution
and the local inspector's composition view.

## Tasks

- [Task 4.3.1 — define ingestion request and reasoning context](task-4.3.1-ingestion-entry-and-reasoning.md)
- [Task 4.3.2 — resolve and create nodes with coherent references](task-4.3.2-node-resolution-and-write.md)
- [Task 4.3.3 — create memory/context objects after their targets](task-4.3.3-memory-context-write.md)
- [Task 4.3.4 — write relationships from resolved endpoints](task-4.3.4-relationship-write.md)
- [Task 4.3.5 — compose the deterministic ingestion workflow](task-4.3.5-ingestion-workflow.md)

The list is an initial breakdown. Issue 4.0 may split, combine, or reorder these
tasks after distinguishing actual agentic states from deterministic workflow
steps. Wire each completed state into the workflow as it is delivered; Task
4.3.5 verifies and completes the whole sequence rather than deferring all
composition until the end.

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

The chatbot's `ingest_memory` tool validates a typed request and invokes the
bound workflow method with source content, owner identity/context, and
relevant conversation/channel context. The precise handoffs are confirmed in
Issue 4.0.
The application binds owner, history, and service dependencies when composing
the workflow tool; they are not model-supplied tool arguments.
As each state is reviewed, define its purpose and input/output first, then its
internal DTOs/artifacts, prompt/history/context, deterministic functions, any
model-visible tools and function mappings, and the next handoff. Local
references remain model-facing handles; backend UUIDs remain behind the mapper.
The typed workflow result returns as one matched tool output to the
conversation-entry state, which owns the final user-facing response.
