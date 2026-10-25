# Task 3.1.1 — migrate graph and owner services used by states

**Status: Candidate capability — activate only when a reviewed state requires it**

## User story

As an application state/tool, I want explicit owner-scoped graph operations,
so model-provided local references are resolved to backend objects only at the
deterministic service boundary.

## What and why

When a reviewed state requires graph/owner behavior, define its functional
service contract within that state slice and adapt only the necessary service.
Preserve backend UUID ownership; do not copy the old agentic tool handler layer.
The examples below are candidates, not a commitment to a standalone graph
service migration.

## Where

- `src/product/graph/`, `src/product/core/owner_context.py`, or the smallest
  equivalent package boundaries justified by current service dependencies.
- Existing graph contract tests and focused owner-isolation tests.

## Functional communication DTOs

The tool/application boundary carries model-local references and trusted owner
context. Its active-workflow/session-scoped mapper resolves references to
persisted UUIDs before calling deterministic services; those services receive
trusted owner identity and typed domain data, not model-local reference syntax.
After a successful create, the mapper associates the new local ref with the
returned UUID. Results returned to the model use the local ref and readable
domain information, never the database UUID as reference identity.

## Dependencies and acceptance

- Depends on Wave 0 graph/owner census and Issue 1.1.1.
- Ownership is applied to every graph operation.
- Graph DTO fields map one-to-one to persisted properties.
- No deterministic duplicate-node blocking or hidden agentic policy is added.
