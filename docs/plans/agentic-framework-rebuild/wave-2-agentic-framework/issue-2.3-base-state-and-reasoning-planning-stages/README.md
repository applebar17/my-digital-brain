# Issue 2.3 — base state and configurable reasoning/planning stages

**Status: In progress — Task 2.3.1 complete; Task 2.3.2 not started**

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

`StateInvocation` carries the caller-selected prompt, history view, one request,
optional structured-output expectation, and toolbox. `StateResult` returns the
provider assistant result and any requested structured artifact or existing
pause/failure outcome. These are state communication contracts, not UI
processing-status DTOs.
