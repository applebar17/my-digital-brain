# Application lifecycle overview

## Purpose

This document shows the application-level journey from an incoming interaction
to persisted or retrieved memory and a user-facing result. It does not define
component ownership, deployment topology, or storage boundaries; those are
owned by [system architecture](system-architecture.md).

Capability-specific user behavior belongs in [flows](../flows/README.md). The
known ingestion state order and typed handoffs belong in
[deterministic agentic workflows](deterministic-agentic-workflows.md). AI
runtime mechanics belong in [AI engineering](../ai-engineering/README.md).

## Lifecycle

1. **Receive:** A channel sends a user request or source artifact to the
   application. The channel boundary normalizes it into an application
   interaction; supported media may produce a linked transcript or other
   derived source.
2. **Process:** The application invokes the capability appropriate to the
   interaction. Ingestion and query journeys are described in the
   [capability flows](../flows/README.md).
3. **Use domain services:** The capability stores or retrieves information
   through the domain services. The meaning and persistence rules for memory
   are owned by [network documentation](../network/README.md).
4. **Respond:** The application returns the result through the originating
   channel.

This is a cross-capability lifecycle, not an execution plan. The ingestion
sequence is specified in the workflow document above; user-visible behavior is
specified in the [functional requirements](../requirements/functional/README.md).

## Related documentation

- [System architecture](system-architecture.md)
- [Deterministic agentic workflows](deterministic-agentic-workflows.md)
- [Flows](../flows/README.md)
- [AI engineering](../ai-engineering/README.md)
- [Network documentation](../network/README.md)
