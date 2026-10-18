# Required AI client layer

## Status

This package is the required target client layer for the rebuilt agentic
framework. It is isolated from active application imports today; its integration
and any narrowly scoped corrections must follow the canonical contracts in
`docs/ai-engineering/` before it is wired into production flows.

The copied `boris.*` import namespace has been replaced with project-local
imports. This makes the package inspectable and independently importable when
its optional provider dependencies are present. The package is the selected
target, but its current implementation is not exempt from comparison with the
accepted DTO, provider, and tool-calling contracts. Fix discrepancies within
this layer; do not add a competing provider/tool loop above agentic states.

## Contents

- `llm_core/`: client parameter handling, provider calls, and the shared tool
  loop exposed to callers through `call(...)`.
- `providers/`: OpenAI, Azure OpenAI, and Anthropic translations.
- `protocols/`: copied message and tool protocol types.
- `dataclasses/`: copied configuration and runtime carriers.
- `utils/`: local helpers used by this package.

## Target boundary

- The client layer owns request parameter management, provider invocation, and
  iterative tool-call execution. OpenAI/Azure-specific request and response
  translation belongs behind its provider adapters.
- Agentic states own state purpose, prompt/context assembly, typed invocation,
  toolbox selection, and result interpretation. They call this client layer;
  they do not implement provider calls or a second tool loop.
- Preserve provider-issued tool-call identifiers through execution and return
  exactly one corresponding tool output to the same client loop.
- Make only the package changes needed to meet the canonical DTO and runtime
  contracts. The technical source of truth is indexed in
  [AI engineering](../../../../docs/ai-engineering/README.md); the target-layer
  boundary is summarized in
  [the client-layer assessment](../../../../docs/ai-engineering/migration/reference-ai-clients-assessment.md).
- Keep provider dependencies explicit and declared before production wiring.
