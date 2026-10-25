# Task 4.3.3 — create memory/context objects after their targets

**Status: Not started**

## User story

As the ingestion workflow, I want memory logs and linked context/perception
objects created with explicit fields and references, so a saved memory is
readable and its target objects already exist.

## What and why

Treat memory-log and context writing as candidate responsibilities until the
state census confirms their boundaries and order. For each resulting state,
agree its functional purpose and input/output before defining its typed DTOs,
deterministic write functions, or model-visible tool. Enforce creation ordering
through workflow handoffs, not by asking the model to invent backend IDs.

## Where

- `product.application.states.ingestion` memory/context states.
- `product.application.tools` and graph persistence DTOs.

## Functional communication boundary

Candidate memory input includes content and references to
resolved entities; candidate context input includes its target references.
These examples do not predefine DTO fields. The approved state task defines
exact inputs/outputs; completed writes return local refs and readable summaries
for the caller or next step.

## Dependencies and acceptance

- Depends on the prior state handoffs agreed in Issue 4.0 and captured in the
  workflow as slices are delivered.
- Define any graph/log DTO or service dependency only for this state's accepted
  functional need.
- Required target object is created/resolved before a linked context is written.
- Memory-log title is a concise generated field, not the full log body by
  default.
- No generic or untyped property bag substitutes for explicit domain fields.
