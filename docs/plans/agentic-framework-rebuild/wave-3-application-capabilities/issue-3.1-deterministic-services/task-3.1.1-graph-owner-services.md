# Task 3.1.1 — migrate graph and owner services used by states

**Status: Not started**

## User story

As an application state/tool, I want explicit owner-scoped graph operations,
so model-provided local references are resolved to backend objects only at the
deterministic service boundary.

## What and why

Move or adapt only graph and owner services used by selected application
states. Preserve backend UUID ownership and current graph DTOs where supported;
do not copy the old agentic tool handler layer.

## Where

- `src/product/graph/`, `src/product/core/owner_context.py`, or the smallest
  equivalent package boundaries justified by current service dependencies.
- Existing graph contract tests and focused owner-isolation tests.

## Functional communication DTOs

Input carries an owner context plus explicit create/read/update data. State
references remain model-facing handles; the application reference context maps
them to graph IDs before the service call. Output identifies the created or
updated domain result and any useful validation/error information, without
exposing database IDs to the model as reference identity.

## Dependencies and acceptance

- Depends on Wave 0 graph/owner census and Issue 1.1.1.
- Ownership is applied to every graph operation.
- Graph DTO fields map one-to-one to persisted properties.
- No deterministic duplicate-node blocking or hidden agentic policy is added.
