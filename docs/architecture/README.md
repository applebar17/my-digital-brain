# Architecture

System decomposition, ownership boundaries, and cross-component data-flow
decisions. The clean-slate AI runtime is specified in `ai-engineering/`; this
folder must not retain a competing agentic-runtime contract.

## Contents

- [Overview](overview.md): system components and their relationships.
- [Agentic orchestration](agentic-orchestration.md): source review required;
  migrate valid functional concepts, then delete.
- [Agentic tool-frame runtime](agentic-tool-frame-runtime.md): source review
  required; migrate valid functional concepts, then delete.
- [Ingestion identity and context packets](ingestion-identity-resolution-and-context-packets.md):
  identity resolution and LLM context boundaries.
- [Memory ingestion planning and refs](memory-ingestion-reasoning-planning-and-llm-refs.md):
  ingestion process contracts and model-facing references.

## Temporary documentation migration ledger

| File | Transaction action |
| --- | --- |
| `overview.md` | Keep, then refresh its AI links to the clean-slate documentation. |
| `agentic-orchestration.md` | Migrate its accepted context rules to `context-and-prompts/context-package-contract.md` and top-level/query behavior to the concrete application-state documents; then continue detailed source review and delete. |
| `agentic-tool-frame-runtime.md` | Migrate its accepted continuation rules to `runtime/agentic-history-session.md` and top-level/query behavior to the concrete application-state documents; then continue detailed source review and delete. |
| `ingestion-identity-resolution-and-context-packets.md` | Detail review required. Migrate accepted identity/context concepts to their specific owner, then delete. |
| `memory-ingestion-reasoning-planning-and-llm-refs.md` | Detail review required. Migrate accepted ingestion/ref concepts to their specific owner, then delete. |

The final folder contains only current cross-component architecture. This table
is removed when the five transactions are complete.
