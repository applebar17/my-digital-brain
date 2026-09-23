# Provider adapters

This folder defines provider-specific adapters and the boundary that shields
the rest of the application from SDK request/response shapes.

## Planned contents

- [Provider integration boundary](provider-integration-boundary.md): OpenAI and
  Azure normalization, capability scope, configuration snapshots, privacy
  handoff, and typed error boundary.
- OpenAI / Azure OpenAI normalization, including provider call-ID mapping.
- Provider capability matrix: tools, strict schemas, structured output,
  streaming, usage, and error metadata.
- Adapter conformance fixtures, captured without secrets.

## Rules

Adapters translate; they do not execute application tools, decide domain
behavior, mutate graph state, or manufacture application IDs. The application
runtime receives only provider-neutral DTOs and returns provider-neutral output
instructions for the adapter to serialize.

## Temporary documentation migration ledger

The provider-specific material from `external-integrations/llm-integration.md`
has moved here. Keep this folder as the sole provider adapter specification;
the ledger disappears when the broader AI documentation migration is complete.
