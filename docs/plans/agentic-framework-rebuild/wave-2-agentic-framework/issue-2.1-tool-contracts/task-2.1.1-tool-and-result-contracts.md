# Task 2.1.1 — define typed tool and result contracts

**Status: Not started**

## User story

As a state author, I want a tool's semantic description, annotated input DTO,
and typed handler signature defined together, so the model contract and
backend function cannot silently drift apart.

## What and why

Implement the minimal generic tool definition and typed registration. The
handler accepts its validated input DTO and returns its annotated success DTO;
bind dependencies when composing the toolbox. Keep provider JSON generation
and the single success/error `ToolOutputDTO` in the client boundary. Do not add
a second result envelope, generic execution context, pending/retryable tool
statuses, or another schema source.

## Where

- `src/product/agentic/tools/` generic contracts and tests.
- `product.ai.ai_clients` adapter boundary only where required to consume the
  descriptor.

## Functional communication DTOs

`ToolDefinitionDTO` communicates name, purpose, and annotated input shape. The
registered handler's return annotation identifies its successful domain output
DTO. The client wraps that data, or a `ToolErrorDTO`, in the existing
`ToolOutputDTO`; provider call ID stays in the client transcript layer.

## Dependencies and acceptance

- Depends on Wave 1 client verification.
- DTO schemas retain field descriptions and enum meanings.
- Handler signatures are annotated and receive the validated `input_dto`.
- Invalid input and handler exceptions become one provider-matched error
  output, after which the invoking model call resumes.
- The handler's return DTO is the sole declaration of its successful output
  type; it is not duplicated as an `output_model` field in the definition.
