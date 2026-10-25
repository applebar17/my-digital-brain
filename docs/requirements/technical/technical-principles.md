# Technical Principles

This document owns repository-wide scope and implementation discipline. It
indexes specialized requirements instead of repeating their domain rules.

## Explicit scope and minimum design

Implement only behavior expressly accepted by the product owner. A proposed
improvement is not authorization to add it. If an unresolved choice would
materially change behavior, a public contract, or data handling, stop and ask
for a decision before implementing it.

Do not add fields, processing states, validation gates, fallback paths, retries,
background jobs, or agentic routing merely because they might be useful. Keep
the smallest design that satisfies the accepted requirement; explain and
propose additional behavior before adding it.

## One owner per behavior

Each functional or technical behavior has one canonical specification and one
active implementation. Do not add duplicate coding logic, parallel
implementations, or legacy code unless the user explicitly requests it. Link to
the canonical owner rather than copying its rules into another document or
module. Remove superseded implementations when they have no remaining supported
caller. If the user requests compatibility code, record its owner and removal
condition.

Cross-boundary DTO and annotation requirements are owned by [Documentation
Conventions](../../documentation-conventions.md). Module layering, inheritance,
acyclic imports, and contextual method documentation are owned by
[Dependency-Oriented Module Design](dependency-oriented-module-design.md).

## Specialized requirement owners

- Product and capability outcomes: [Product Foundation](../product-foundation.md)
  and [Functional Requirements](../functional/README.md).
- Service topology, data stores, and deployment boundaries: [System
  Architecture](../../architecture/system-architecture.md).
- Graph, evidence, identity, memory lifecycle, time, affect, and metadata:
  [Network requirements](../../network/README.md).
- Privacy and trust: [Privacy and Trust](../privacy-and-trust.md).
- AI models, tools, runtime continuation, prompts, and state behavior: [AI
  Engineering](../../ai-engineering/README.md).
- User-visible chat, graph, analytics, and accessibility: [UI
  Requirements](../ui/README.md).
