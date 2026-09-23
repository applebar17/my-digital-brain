# Architecture

System decomposition, ownership boundaries, and cross-component data-flow
decisions. The clean-slate AI runtime is specified in `ai-engineering/`; this
folder must not retain a competing agentic-runtime contract.

## Contents

- [Overview](overview.md): system components and their relationships.
- [Deterministic agentic workflows](deterministic-agentic-workflows.md): MVP
  workflow scheduling, typed handoffs, phase dependencies, and future
  coordinator replacement boundary.
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
| `overview.md` | Keep, then refresh its AI links to the clean-slate documentation and its component responsibilities after the workflow migration. |
| `deterministic-agentic-workflows.md` | Current MVP workflow coordination contract. Keep and refine with concrete ingestion state DTOs. |
| `agentic-orchestration.md` | Review complete. Its state, context, toolbox, and prompt principles have canonical AI-engineering owners; its pending-process and handoff runtime is retired. Delete after final inbound-link review. |
| `agentic-tool-frame-runtime.md` | Review complete. Its provider continuation and compact nested-result rules have canonical runtime/history owners; its `AgenticFrame` and generic plan executor are retired. Delete after final inbound-link review. |
| `ingestion-identity-resolution-and-context-packets.md` | Retained reference safety, bounded lookup evidence, and additive-update rules are migrated to AI context/workflow contracts. Its rigid lookup stage, static `OWNER`, and resolution machinery are retired; delete after final inbound-link review. |
| `memory-ingestion-reasoning-planning-and-llm-refs.md` | Retained reference rendering, bounded packet, reasoning-boundary, and phased ingestion dependency rules are migrated. Its generic plan/action executor and prompt-registry design are retired; delete after final inbound-link review. |

The final folder contains only current cross-component architecture. This table
is removed when the five transactions are complete.
