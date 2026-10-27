# Task 4.3.5 — write relationships from resolved endpoints

**Status: Not started**

## User story

As the ingestion workflow, I want relationship proposals grounded in the
provided input and written only after their endpoints resolve, so meaningful
relationships are represented without inventing participants.

## What and why

Implement `RelationshipWriteState` as the final write state. Define its typed
input/output, allowed relationship data, prompt guidance, deterministic write
function, graph-tool mapping, clarification capability, and workflow handoff
together. Execute writes against resolved local endpoint refs. Preserve failed
writes as recoverable tool outputs; reconciliation of missing edges remains
outside scope unless separately prioritized.

The state uses one main LLM/tool session with no separate framework
reasoning/planning stage.

## Where

- Relationship-write state/prompt under `product.application.states.ingestion`.
- Typed graph relationship DTO and write tool under `product.application`.

## Functional communication boundary

Input includes inherited history, reasoning and memory/context outcomes, and
resolved endpoint local refs. A completed write returns the functional
relationship result and readable summary; backend IDs remain internal.

## Dependencies and acceptance

- Depends on whichever earlier state resolves the required endpoints and
  creates any required relationship context, as confirmed by Issue 4.0.
- Allowed relationship schema matches the graph's supported kinds.
- Each endpoint resolves to an existing/created object before the write call.
- No relationship omission is silently reported as successful creation.
