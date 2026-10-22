# Issue 2.3 — base state and configurable reasoning/planning stages

**Status: Complete**

Implement the generic state entrypoint that opens a local conversation and
delegates to `LLMInterfaceCore.call(...)`. A concrete state may also configure
purpose-specific reasoning and/or planning LLM stages as part of its execution;
these are not generic preparation callbacks or mandatory for every state.

## Tasks

- [Task 2.3.1 — implement invocation and result boundary](task-2.3.1-base-state.md)
- [Task 2.3.2 — configure reasoning and planning stages](task-2.3.2-reasoning-planning-stages.md)

## Dependencies

- [Agentic state framework](../../../../ai-engineering/runtime/agentic-state-framework.md)
- [Configurable reasoning and planning stages](../../../../ai-engineering/runtime/agentic-state-reasoning-and-planning.md)

## Functional communication DTOs

`AgenticStateInvocationDTO` carries the caller-selected prompt, history view,
request, optional main response model and toolbox, and optional stage
configurations. `AgenticStateResultDTO` returns the provider assistant result
and any requested structured artifact or existing pause/failure outcome. A
stage pause uses the existing continuation DTO with its internal stage cursor;
this is not a UI processing-status contract.
