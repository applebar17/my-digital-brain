# Task 4.3.2 — resolve and create nodes with coherent references

**Status: Not started**

## User story

As the ingestion workflow, I want node candidates and known graph identities
represented in a shared model-facing reference context, so later steps can
reuse the correct identity or create a distinct one without seeing backend IDs.

## What and why

Implement candidate understanding/resolution and explicit typed node writes.
The state may choose an existing or new identity based on full context; only
duplicate use of the same local ref is incoherent. Ambiguity that materially
changes identity can invoke the clarification child state.

## Where

- `product.application.states.ingestion` node-candidate/resolution states.
- `product.application.tools` graph node create/update bindings and the
  per-ingestion reference context.

## Functional communication DTOs

Candidate input: source evidence and readable known-node/reference inventory.
Resolution result: selected existing local ref, new-node proposal with typed
fields, or clarification request. Write result: persisted graph object mapped
back to its local ref and readable identity/summary for subsequent states.

## Dependencies and acceptance

- Depends on Tasks 3.1.1, 3.2.1, 4.3.1, and clarification tasks when needed.
- Reference rendering uses the accepted verbosity and owner conventions.
- Node DTO fields correspond explicitly to graph properties.
- A tool validation/write error returns an explanatory tool result; it does not
  deterministically terminate the whole model interaction.
