# Task 4.3.4 — create memory/context objects after their targets

**Status: Not started**

## User story

As the ingestion workflow, I want memory logs and linked context/perception
objects created with explicit fields and references, so a saved memory is
readable and its target objects already exist.

## What and why

Implement `MemoryContextWriteState` after node resolution. Define its typed
input/output, prompt, deterministic write functions, graph-tool mappings, and
workflow handoff together. Enforce creation ordering through workflow
dependencies, not by asking the model to invent backend IDs.

The state uses one main LLM/tool session with no separate framework
reasoning/planning stage. It may invoke clarification for a material gap and
then resumes the same session before the workflow advances.

## Where

- `product.application.states.ingestion` memory/context states.
- `product.application.tools` and graph persistence DTOs.

## Functional communication boundary

Input includes inherited history, the reasoning result, resolved entity refs,
and relevant prior outcomes. Output contains explicit memory-log and linked
context write outcomes. Completed writes return local refs and readable
summaries for the caller or next step.

## Dependencies and acceptance

- Depends on the prior state handoffs agreed in Issue 4.0 and captured in the
  workflow as slices are delivered.
- Define any graph/log DTO or service dependency only for this state's accepted
  functional need.
- Required target object is created/resolved before a linked context is written.
- Memory-log title is a concise generated field, not the full log body by
  default.
- No generic or untyped property bag substitutes for explicit domain fields.
