# Task 4.3.5 — write relationships from resolved endpoints

**Status: Not started**

## User story

As the ingestion workflow, I want relationship proposals grounded in the
provided input and written only after their endpoints resolve, so meaningful
relationships are represented without inventing participants.

## What and why

Implement `RelationshipWriteState` as the final write state. This task owns
durable graph relationships, `RelationshipContext`, and the relationship-state
history needed to represent changes over time. Define their typed input/output,
allowed relationship data, prompt guidance, deterministic write functions,
graph-tool mappings, clarification capability, and workflow handoff together.
Execute writes against resolved local endpoint refs. Preserve failed writes as
recoverable tool outputs; reconciliation of missing edges remains outside scope
unless separately prioritized.

The task must wire relationship context end to end: accept resolved participant
refs and relevant `MemoryLog` refs from Task 4.3.4; create or select the
relationship context before writing dependent relationship-state/history links;
bind every created context to the shared `ReferenceContext`; and return readable
context and relationship outcomes to the workflow. It must define explicitly
whether a new observation creates a new relationship-state record or updates
only the current durable edge, without silently flattening history.

The state uses one main LLM/tool session with no separate framework
reasoning/planning stage.

## Where

- Relationship-write state/prompt under `product.application.states.ingestion`.
- Typed graph relationship DTO and write tool under `product.application`.

## Functional communication boundary

Input includes inherited history, reasoning, memory/perception outcomes,
resolved endpoint local refs, and relevant memory refs. A completed write
returns the functional relationship/context result and readable summary;
backend IDs remain internal.

## Dependencies and acceptance

- Depends on whichever earlier state resolves the required endpoints and
  creates any required relationship context, as confirmed by Issue 4.0.
- Allowed relationship schema matches the graph's supported kinds.
- Each endpoint resolves to an existing/created object before the write call.
- Relationship-context creation precedes every dependent relationship-state or
  memory-context link, and all of them use the same run-scoped references.
- DTOs and tools explicitly cover creation versus update of durable edges,
  relationship contexts, and relationship-state history without an untyped
  property bag.
- No relationship omission is silently reported as successful creation.
