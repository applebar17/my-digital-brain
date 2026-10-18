# Task 1.2.1 — locate `ai_clients` under `product`

**Status: In progress**

## User story

As the application, I want the selected provider client available as
`product.ai.ai_clients`, so the new framework uses the accepted provider and
tool-loop implementation rather than importing old session code.

## What and why

Move the selected package and its shared tracing dependency into the target
namespace, rebase internal imports, and retain its module layering. This task is
a path/import migration only; contract and dependency alignment is intentionally
deferred to the later Wave 1 review task.

## Where

- `src/product/ai/ai_clients/` and its internal imports.
- Shared tracing utility at `src/product/ai/tracing.py` and existing callers
  that need this common utility.
- `pyproject.toml` and AI-engineering references to the selected client path.

## Functional communication DTOs

No new semantics. The package retains provider-neutral request configuration,
message history, typed tool calls/results, structured output, and final client
response as defined in the [client assessment](../../../../ai-engineering/migration/reference-ai-clients-assessment.md).

## Dependencies and acceptance

- Depends on Task 1.1.1.
- Public client entrypoint and required provider adapters import from `product`.
- Client modules have no import back into `my_digital_brain`.
- Existing application code can continue using the shared tracer without a
  duplicated implementation.
- No provider/tool-loop logic is copied into `product.agentic`.
