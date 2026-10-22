# Issue 2.3 — base state and optional preparation

**Status: In progress — Task 2.3.1 complete; Task 2.3.2 not started**

Implement the generic state entrypoint that prepares a local conversation and
delegates exactly once to `LLMInterfaceCore.call(...)`. Optional reasoning and
planning are configured state preparations, not a second runtime or a required
pipeline for every state.

## Tasks

- [Task 2.3.1 — implement invocation and result boundary](task-2.3.1-base-state.md)
- [Task 2.3.2 — configure reasoning and planning preparation](task-2.3.2-state-preparation.md)

## Dependencies

- [Agentic state framework](../../../../ai-engineering/runtime/agentic-state-framework.md)
- [Reasoning/planning preparation](../../../../ai-engineering/runtime/agentic-state-preparation.md)

## Functional communication DTOs

`StateInvocation` carries the caller-selected prompt, history view, one request,
optional structured-output expectation, and toolbox. `StateResult` returns the
provider assistant result and any requested structured artifact or existing
pause/failure outcome. These are state communication contracts, not UI
processing-status DTOs.
