# Task 4.1.2b — implement shared model-reference context

**Status: Completed**

## User story

As a workflow, state, or model-facing tool, I need one run-scoped reference
context that allocates readable local identifiers and privately maps them to
backend identities, so every LLM process uses coherent references without
seeing database UUIDs.

## What and why

Implement the canonical
[ReferenceContext](../../../../ai-engineering/context-and-prompts/reference-context-and-owner-projection.md)
before exposing deterministic search as a tool. Existing `RefContext` and
`RunReferenceRegistry` implementations are migration evidence, not target
classes. Build one small shared implementation and retire rather than copy
their overlapping behavior when their active callers migrate.

This task activates the reference-mapping boundary anticipated by the Wave 3
[graph/owner service task](../../wave-3-application-capabilities/issue-3.1-deterministic-services/task-3.1.1-graph-owner-services.md)
and [product-tool task](../../wave-3-application-capabilities/issue-3.2-product-tools/task-3.2.1-read-and-write-tools.md).

## Functional behavior

One `ReferenceContext` instance belongs to a top-level agentic interaction or
workflow execution. Application composition passes that same instance to its
child states, deterministic tools, and workflows. It is not a global registry,
conversation history, or database identity service.

The service must support:

- registering a persisted object and allocating a new model-facing reference
  when its backend ID has not been seen in the current run;
- reusing the same local reference whenever that backend ID appears again;
- resolving a supplied local reference to its private backend ID before a
  deterministic service call;
- allocating a proposed local reference before an object has a backend ID;
- binding that proposed reference to the UUID returned by a successful write;
- maintaining explicit object kind, label, display name, summary, aliases, and
  resolution status in its model-facing entry;
- producing and merging typed reference deltas for dependent child-state or
  workflow handoffs;
- rendering selected entries at canonical verbosity levels zero through two.

Reference allocation follows the canonical families and is backend-owned. A
tool field may explain the expected object kind and ask for a supplied active
reference, but it must not hardcode an illustrative counter width or accept a
model-invented backend identity.

## Boundary and package structure

- `src/product/application/references/models.py` owns reference kinds,
  statuses, entries, deltas, and private mapping contracts.
- `service.py` owns allocation, registration, reverse lookup, post-write
  binding, and delta merging.
- `renderer.py` owns levels zero through two; states and tools do not duplicate
  reference prose.

The private backend mapping never appears in a model-facing entry or rendered
section. Unknown or incompatible local references raise a clear deterministic
error that the generic tool layer can return to the invoking LLM for repair.

## Acceptance

- Two registrations of one backend ID return the same local reference.
- Newly discovered search nodes and relationships receive references even when
  they were absent from the initial context.
- Relationship endpoints reuse their nodes’ existing references.
- Proposed references can be bound after successful creation without changing
  the identifier already seen by the LLM.
- Backend UUIDs are absent from model projections and all rendering levels.
- The same instance can be injected into memory search and later ingestion
  workflow composition without compatibility adapters or duplicate registries.
