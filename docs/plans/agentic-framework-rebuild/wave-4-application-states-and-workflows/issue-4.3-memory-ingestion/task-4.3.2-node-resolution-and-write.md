# Task 4.3.2 — resolve and create nodes with coherent references

**Status: Not started**

## User story

As the ingestion workflow, I want node candidates and known graph identities
represented in a shared model-facing reference context, so later steps can
reuse the correct identity or create a distinct one without seeing backend IDs.

## What and why

The current title and behavior are a candidate for the node-related slice, not
an assumption that candidate extraction, identity resolution, and persistence
belong in one agentic state. Use the Issue 4.0 census to identify the actual
state boundary first. Then define its purpose, input/output, internal DTOs,
deterministic lookup/write dependencies, and any model-visible tool mappings.
The state may choose an existing or new identity from full context; local refs
are mapped to backend UUIDs at the tool/service boundary.

## Where

- `product.application.states.ingestion` node-candidate/resolution states.
- `product.application.tools` graph node create/update bindings and the
  per-ingestion reference context.

## Functional communication boundary

Candidate input/result above is a working example only. Agree the actual
state's input/output and whether resolution and writing are one or separate
steps before defining concrete DTOs. Any write result used downstream returns a
local ref and readable identity/summary, not a backend UUID.

## Dependencies and acceptance

- Depends on the approved state order and relevant prior handoff from Issue
  4.0/4.3.1.
- Pull in only the deterministic graph capability or child-state tool required
  by this state's agreed behavior; do not wait for Wave 3 as a whole.
- Reference rendering uses the accepted verbosity and owner conventions.
- Node DTO fields correspond explicitly to graph properties.
- A tool validation/write error returns an explanatory tool result; it does not
  deterministically terminate the whole model interaction.
