# Architecture

System-level boundaries and coordination. Component ownership and topology
live in one document; the lifecycle overview and workflow sequence have
separate scopes. AI runtime mechanics are indexed in
[AI engineering](../ai-engineering/README.md).

## Contents

- [Application lifecycle overview](overview.md): cross-capability journey from
  incoming interaction to a user-facing result.
- [System architecture](system-architecture.md): high-level consumers,
  component responsibilities, external services, storage, and deployment
  posture; canonical owner of component boundaries.
- [Deterministic agentic workflows](deterministic-agentic-workflows.md): MVP
  workflow base, typed handoffs, dependency execution, and future coordinator
  replacement boundary.
- [Memory-ingestion workflow map](memory-ingestion-workflow-map.md): canonical
  flow diagrams, functional handoffs, and per-state call profiles.
