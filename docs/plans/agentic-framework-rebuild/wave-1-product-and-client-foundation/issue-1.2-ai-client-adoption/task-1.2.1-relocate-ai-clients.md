# Task 1.2.1 — locate `ai_clients` under `product`

**Status: Not started**

## User story

As the application, I want the selected provider client available as
`product.ai.ai_clients`, so the new framework uses the accepted provider and
tool-loop implementation rather than importing old session code.

## What and why

Move/adapt the selected package into the target namespace, keep its internal
module layering, and declare only dependencies that are actually required.
Preserve its provider/adapter separation and avoid a second client package.

## Where

- `src/product/ai/ai_clients/` and its package imports.
- Dependency and test configuration; retain old package files until cutover if
  existing application imports still need them.

## Functional communication DTOs

No new semantics. The package retains provider-neutral request configuration,
message history, typed tool calls/results, structured output, and final client
response as defined in the [client assessment](../../../../ai-engineering/migration/reference-ai-clients-assessment.md).

## Dependencies and acceptance

- Depends on Task 1.1.1.
- Public client entrypoint and required provider adapters import from `product`.
- Dependencies are declared and tests run without relying on undeclared
  environment packages.
- No provider/tool-loop logic is copied into `product.agentic`.
