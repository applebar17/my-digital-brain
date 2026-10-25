# Task 4.P.1 — expose assembled workflow and run inspection data

**Status: Not started**

## User story

As a developer, I want a typed, read-only inspection boundary for workflow
composition and execution, so the local viewer can report what was actually
configured and what happened during a run.

## What and why

Introduce a small `BaseWorkflow` inherited by concrete workflows. Its explicit
step declarations drive dependency execution and expose the same ordered or
independent-step graph to the inspector. Adapt the generic agentic state/toolbox
boundaries to expose concise descriptions and DTO contract summaries. Include
state purpose, configured reasoning/planning stages and artifacts, main call,
prompt identity and versioned template, input/output DTO fields derived from
annotations, and registered toolbox definitions. Show effective toolbox
selection for an invocation when it differs from the state's declared
capabilities.

At workflow and state boundaries, expose the step identity, typed input/result,
and progression needed to place a selected run on the composition map. Tool
calls and their outcomes remain attached to their owning state. When a tool
invokes a child agentic state, expose the parent-child link and the child's
own tool calls and result; clarification must be visible as such a child. Use
the existing developer trace mechanism where suitable; do not make a parallel
execution store or infer state progress from provider messages.

## Where and contracts to define during implementation

- Target workflow base and composition: `src/product/application/workflows/`.
- Target state/toolbox inspection: `src/product/agentic/` and its DTOs; exact
  modules follow the accepted Wave 2 code.
- Target developer API: `src/product/api/` or the adapted stable debug route.
- Read-only composition DTO: ordered and independent step descriptions and
  dependencies, including agentic configuration, prompt/toolbox metadata,
  and typed handoff summaries.
- Read-only run DTO: run-to-step association, observed input/output values,
  tool outcomes, parent-child state links, and enough timing/progression to
  highlight the actual path.

The DTO names and field shapes are agreed with the task before coding. Their
content is derived from the assembled workflow step declarations, annotated
callables, referenced state/toolbox objects, and existing runtime events.

## Verification

Use one small `BaseWorkflow` subclass to verify that inspection reports the
same order and dependency links used by execution, plus state call
configuration, prompt, toolbox, and input/output contracts. Run it
through one state/tool handoff and confirm the run view matches that execution.
Keep this scenario useful when the first product workflow replaces the sample.
