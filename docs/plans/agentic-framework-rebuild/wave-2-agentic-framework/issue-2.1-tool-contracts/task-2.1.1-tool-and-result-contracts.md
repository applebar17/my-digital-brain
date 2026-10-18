# Task 2.1.1 — define typed tool and result contracts

**Status: Not started**

## User story

As a state author, I want a tool's semantic description, annotated input DTO,
output DTO, and handler signature defined together, so the model contract and
backend function cannot silently drift apart.

## What and why

Implement the documented generic tool descriptor, registration, typed
execution context, and output/error envelope. Keep provider JSON generation in
the client adapter and do not create another schema source.

## Where

- `src/product/agentic/tools/` generic contracts and tests.
- `product.ai.ai_clients` adapter boundary only where required to consume the
  descriptor.

## Functional communication DTOs

`ToolDefinition` communicates name, purpose, annotated input shape, and typed
output meaning. `ToolExecutionContext` carries only explicit invocation
resources. `ToolResult` communicates success data or an explanatory error to
the invoking state; provider call ID stays in the client transcript layer.

## Dependencies and acceptance

- Depends on Wave 1 client verification.
- DTO schemas retain field descriptions and enum meanings.
- Handler signatures are annotated and receive `(context, input_dto)`.
- An exception becomes one error result; no framework-level deterministic
  process stop is added.
