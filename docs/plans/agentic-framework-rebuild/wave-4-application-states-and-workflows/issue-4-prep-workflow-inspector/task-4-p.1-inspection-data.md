# Task 4.P.1 — expose assembled workflow and run inspection data

**Status: Complete**

## User story

As a developer, I want a typed, read-only inspection boundary for workflow
composition, so the local viewer can report what was actually configured.

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

This first slice exposes configuration only. Do not introduce run-event
persistence, a duplicate trace store, or a prompt-version field that the
current runtime cannot supply. A sample agentic step may be configuration-only
until the first real agentic workflow is implemented; label it as such.

## Where and contracts to define during implementation

- Target workflow base and composition: `src/product/application/workflows/`.
- Target state/toolbox inspection: `src/product/agentic/` and its DTOs; exact
  modules follow the accepted Wave 2 code.
- Target local inspector: `src/product/dev/` and a local startup script; no
  application API route is required.
- Read-only composition DTO: ordered and independent step descriptions and
  dependencies, including agentic configuration, prompt/toolbox metadata,
  and typed handoff summaries.

The DTO names and field shapes are agreed with the task before coding. Their
content is derived from the assembled workflow step declarations, annotated
callables, referenced state/toolbox objects, and existing runtime events.

## Verification

Use one small `BaseWorkflow` subclass to verify that inspection reports the
same order and dependency links used by execution, plus state call
configuration, prompt, toolbox, and input/output contracts. Verify a typed
handoff and the local inspection endpoint. No provider call is needed for the
sample; keep it visibly labelled until the first product workflow replaces it.
