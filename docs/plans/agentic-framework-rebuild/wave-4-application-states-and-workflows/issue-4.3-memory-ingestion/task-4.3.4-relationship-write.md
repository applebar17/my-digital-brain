# Task 4.3.4 — write relationships from resolved endpoints

**Status: Not started**

## User story

As the ingestion workflow, I want relationship proposals grounded in the
provided input and written only after their endpoints resolve, so meaningful
relationships are represented without inventing participants.

## What and why

Confirm from the state census whether relationship writing is a distinct state
or part of another state. If needed, agree its functional purpose and
input/output first, then define the allowed relationship data, prompt examples,
deterministic function, and model-visible tool mapping. Execute writes against
resolved local endpoint refs. Preserve failed writes as recoverable tool
outputs; reconciliation of missing edges remains outside scope unless separately
prioritized.

## Where

- Relationship-write state/prompt under `product.application.states.ingestion`.
- Typed graph relationship DTO and write tool under `product.application`.

## Functional communication boundary

Candidate input includes the relevant input context and resolved endpoint local refs.
Agree the exact input/output DTO only if the census confirms this state is
needed. A completed write returns the functional relationship result and
readable summary; backend IDs remain internal.

## Dependencies and acceptance

- Depends on whichever earlier state resolves the required endpoints and
  creates any required relationship context, as confirmed by Issue 4.0.
- Allowed relationship schema matches the graph's supported kinds.
- Each endpoint resolves to an existing/created object before the write call.
- No relationship omission is silently reported as successful creation.
