# Wave 3 — application capabilities

**Status: Not started**

## Outcome

Expose the deterministic capabilities needed by application states as explicit
services and typed tools under `product.application`. Models choose tools;
backend services perform graph, retrieval, and clarification operations.

## Issues

- [Issue 3.1 — migrate deterministic services required by the MVP](issue-3.1-deterministic-services/README.md)
- [Issue 3.2 — define product tool DTOs and bindings](issue-3.2-product-tools/README.md)

## Dependencies and boundaries

- Depends on the typed generic contracts in Wave 2.
- Existing graph, vector, chat, and clarification service contracts are
  inventoried in [Wave 0](../wave-0-census/README.md).
- Do not move a service just to match a desired folder; move the minimal
  dependencies required by the agreed application states.

## Exit evidence

- Every tool exposed to a model has an explicit typed input and functional
  output DTO and maps to one deterministic service or child state.
- No application agentic policy is placed inside graph/vector storage classes.
