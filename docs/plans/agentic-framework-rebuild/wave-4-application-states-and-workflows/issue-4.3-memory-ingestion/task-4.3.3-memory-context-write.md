# Task 4.3.3 — create memory/context objects after their targets

**Status: Not started**

## User story

As the ingestion workflow, I want memory logs and linked context/perception
objects created with explicit fields and references, so a saved memory is
readable and its target objects already exist.

## What and why

Implement the typed memory-log and context write state/tool contracts, including
human-readable titles/summaries and source evidence where required. Enforce
creation ordering through the workflow dependency, not by asking the model to
invent backend IDs.

## Where

- `product.application.states.ingestion` memory/context states.
- `product.application.tools` and graph persistence DTOs.

## Functional communication DTOs

Memory input includes content/title, happened-at context when known, source
evidence, and references to resolved entities. Context/perception input
includes type, description/evidence, and its already-created target refs.
Outputs return local refs and readable summaries for later steps and the
invoking agent.

## Dependencies and acceptance

- Depends on Task 4.3.2 and graph/log DTOs from Wave 3.
- Required target object is created/resolved before a linked context is written.
- Memory-log title is a concise generated field, not the full log body by
  default.
- No generic or untyped property bag substitutes for explicit domain fields.
