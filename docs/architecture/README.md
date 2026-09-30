# Architecture

System decomposition, ownership boundaries, and cross-component data-flow
decisions. The clean-slate AI runtime is specified in `ai-engineering/`; this
folder must not retain a competing agentic-runtime contract.

## Contents

- [Overview](overview.md): system components and their relationships.
- [System architecture](system-architecture.md): high-level consumers,
  application boundaries, external services, storage, and deployment posture.
- [Deterministic agentic workflows](deterministic-agentic-workflows.md): MVP
  workflow scheduling, typed handoffs, phase dependencies, and future
  coordinator replacement boundary.
- [Architecture documentation migration](architecture-documentation-migration.md):
  temporary keep/move/delete plan for this folder; delete it when complete.

## Temporary documentation migration ledger

| File | Transaction action |
| --- | --- |
| `overview.md` | Keep, then refresh its AI links to the clean-slate documentation and its component responsibilities after the workflow migration. |
| `deterministic-agentic-workflows.md` | Current MVP workflow coordination contract. Keep and refine with concrete ingestion state DTOs. |
| `agentic-orchestration.md` | Retired in Wave 2; its retained rules have canonical AI-engineering owners. |
| `agentic-tool-frame-runtime.md` | Retired in Wave 2; its retained rules have canonical runtime and history owners. |
| `ingestion-identity-resolution-and-context-packets.md` | Retired in Wave 2; its retained rules have canonical context and workflow owners. |
| `memory-ingestion-reasoning-planning-and-llm-refs.md` | Retired in Wave 2; its retained rules have canonical state, context, and preparation owners. |

The final folder contains only current cross-component architecture. This table
is removed when the five transactions are complete.
