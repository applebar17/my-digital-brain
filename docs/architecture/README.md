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
| `agentic-orchestration.md` | Review with the product owner. Migrate only still-valid functional decisions into named `ai-engineering/` or flow documents, then delete. |
| `agentic-tool-frame-runtime.md` | Review with the product owner. Migrate only still-valid functional decisions into named `ai-engineering/` or flow documents, then delete. |
| `ingestion-identity-resolution-and-context-packets.md` | Detail review required. Migrate accepted identity/context concepts to their specific owner, then delete. |
| `memory-ingestion-reasoning-planning-and-llm-refs.md` | Detail review required. Migrate accepted ingestion/ref concepts to their specific owner, then delete. |

The final folder contains only current cross-component architecture. This table
is removed when the five transactions are complete.
