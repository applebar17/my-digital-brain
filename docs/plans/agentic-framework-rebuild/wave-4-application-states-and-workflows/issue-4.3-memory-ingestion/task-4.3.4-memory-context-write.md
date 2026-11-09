# Task 4.3.4 — create memory/context objects after their targets

**Status: Completed — final workflow composition remains in Task 4.3.6**

## User story

As the ingestion workflow, I want memory logs and linked context/perception
objects created with explicit fields and references, so a saved memory is
readable and its target objects already exist.

## What and why

Implement `MemoryContextWriteState` after node resolution. This task owns
`MemoryLog` and `Perception` creation only. Define its typed input/output,
prompt, deterministic write functions, graph-tool mappings, and workflow
handoff together. Enforce creation ordering through workflow dependencies, not
by asking the model to invent backend IDs.

`RelationshipContext` and its state/history wiring are explicitly owned by
Task 4.3.5. That later task consumes the resolved node refs and created memory
refs from this state, creates the relationship context before dependent links,
and returns its context ref through the same shared `ReferenceContext`.

The delivered vertical slice includes the state, prompt, typed MemoryLog and
Perception contracts, deterministic persistence boundary, tool mappings,
reference binding, inspector configuration, and functional tests. Task 4.3.6
places this state after the deferred node-resolution batch loop and carries its
typed result into relationship work; no partial duplicate workflow path is
introduced here.

The state uses one main LLM/tool session with no separate framework
reasoning/planning stage. It may invoke clarification for a material gap and
then resumes the same session before the workflow advances.

## Where

- `product.application.states.ingestion` memory/context states.
- `product.application.tools` and graph persistence DTOs.

## Functional communication boundary

Input includes inherited history, the reasoning result, resolved entity refs,
and relevant prior outcomes. Output contains explicit memory-log and perception
write outcomes. Completed writes return local refs and readable summaries for
the caller or next step.

## Dependencies and acceptance

- Depends on the prior state handoffs agreed in Issue 4.0 and captured in the
  workflow as slices are delivered.
- Define any graph/log DTO or service dependency only for this state's accepted
  functional need.
- Required target object is created/resolved before a linked context is written.
- Memory-log title is a concise generated field, not the full log body by
  default.
- A perception targets an already resolved domain node. Relationship context,
  relationship state/history, and links from a memory log to those objects are
  deferred to Task 4.3.5.
- No generic or untyped property bag substitutes for explicit domain fields.
