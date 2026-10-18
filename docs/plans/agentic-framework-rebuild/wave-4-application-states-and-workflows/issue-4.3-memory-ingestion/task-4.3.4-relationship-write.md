# Task 4.3.4 — write relationships from resolved endpoints

**Status: Not started**

## User story

As the ingestion workflow, I want relationship proposals grounded in source
evidence and written only after their endpoints resolve, so meaningful
relationships are represented without inventing participants.

## What and why

Define relationship kinds and fields from the graph contract, ensure the model
has examples of broad relationship categories, and execute writes against
resolved local endpoint refs. Preserve failed writes as recoverable tool
outputs; future reconciliation of missing edges is outside this task unless
separately prioritized.

## Where

- Relationship-write state/prompt under `product.application.states.ingestion`.
- Typed graph relationship DTO and write tool under `product.application`.

## Functional communication DTOs

Input: source evidence, allowed relationship categories, endpoint local refs,
and any relevant temporal/status context. Output: written relationship local
ref, endpoints, readable type/summary, and explicit error information if the
write fails.

## Dependencies and acceptance

- Depends on Task 4.3.2 for endpoints and Task 4.3.3 when relationship context
  must be attached.
- Allowed relationship schema matches the graph's supported kinds.
- Each endpoint resolves to an existing/created object before the write call.
- No relationship omission is silently reported as successful creation.
