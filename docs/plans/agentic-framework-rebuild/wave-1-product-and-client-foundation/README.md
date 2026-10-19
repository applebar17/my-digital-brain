# Wave 1 — product namespace and client foundation

**Status: Done**

## Outcome

Create the destination package boundary and establish the selected
`ai_clients` package at `product.ai.ai_clients`. The current application remains
available during migration; this wave does not bulk-rename every source module.

## Issues

- [Issue 1.1 — establish the `product` package boundary](issue-1.1-product-package-boundary/README.md)
- [Issue 1.2 — adopt and verify the selected AI client layer](issue-1.2-ai-client-adoption/README.md)

## Dependencies and boundaries

- Depends on Wave 0 census being complete.
- Client/provider/tool-loop rules remain owned by
  [AI engineering](../../../ai-engineering/README.md).
- `my_digital_brain` remains the current application until final cutover; new
  framework code must not import old agentic runtime modules.

## Exit evidence

- `product` package is discoverable by local development, tests, and packaging.
- `product.ai.ai_clients` can make configured provider calls and execute typed
  mapped tools according to the canonical protocol.
- The old namespace is not retained as a permanent compatibility alias.
