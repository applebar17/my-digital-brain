# Reference AI clients

## Status

This package is the isolated migration source for the future AI client/runtime.
It is not imported by the active application yet and must not be wired into
production flows before the DTO-first migration waves are implemented.

The copied `boris.*` import namespace has been replaced with project-local
imports. This makes the package inspectable and independently importable when
its optional provider dependencies are present; it does not make its current
tool-loop implementation the canonical runtime.

## Contents

- `llm_core/`: reference client orchestration and its original tool loop.
- `providers/`: OpenAI, Azure OpenAI, and Anthropic translations.
- `protocols/`: copied message and tool protocol types.
- `dataclasses/`: copied configuration and runtime carriers.
- `utils/`: local helpers used by the reference package.

## Migration rules

- Do not import this package from active `chat`, `ingestion`, or `agentic` code.
- Port behavior only through the documented DTO and runtime contracts.
- Replace copied dataclasses and loose mappings with Pydantic DTOs before use.
- Declare or remove each optional dependency before the package becomes an
  application dependency.
