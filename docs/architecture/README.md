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
