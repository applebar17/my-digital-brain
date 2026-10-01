# AI engineering

Canonical documentation for the application's AI contracts, runtime,
application states, providers, prompts, and observability. Each topic is owned
by one focused document; this page only indexes those owners.

## Contents

- [Foundations](foundations/README.md): entry point to cross-cutting AI design
  constraints and their canonical owners.
- [Contracts](contracts/README.md): DTO-first boundaries, tool declarations,
  outputs, errors, and structured model results.
- [Runtime](runtime/README.md): agentic states, history, preparation calls, and
  provider tool-call continuation.
- [Application states](application-states/README.md): application capabilities
  classified as deterministic tools, LLM-only states, or dynamic states.
- [Providers](providers/README.md): external AI capability adapters and
  provider-neutral configuration boundaries.
- [Context and prompts](context-and-prompts/README.md): model-facing context,
  reference rendering, prompt authoring, and prompt versions.
- [Observability and evaluation](observability-and-evaluation/README.md):
  traces, diagnostics, fixtures, and regression evaluation.
- [Migration](migration/README.md): active implementation transition records.

## How to use this section

Start with the document that owns the boundary being changed. Update that
document when its contract changes, then update its folder index if its contents
or navigation change. Link to the owner from other documents instead of
repeating its rules here.
