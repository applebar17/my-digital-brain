# Observability and evaluation

This folder defines what must be observable and testable for AI behavior to be
debuggable by both product owners and engineers.

## Planned contents

- Human-readable execution trace contract.
- Provider and runtime diagnostic fields.
- Tool-call correlation and replay policy.
- Scenario fixtures and regression evaluations.

## Principle

Traces record the cause, scope, and outcome of a state or tool operation. They
must separate user-safe activity summaries from technical diagnostics. Raw
provider payloads, prompts, and sensitive source data are retained only under
the project privacy policy.
