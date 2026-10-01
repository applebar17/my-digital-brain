# My Digital Brain Documentation

This documentation describes the foundation for a personal digital brain: a graph-based memory system that ingests user-provided information, extracts entities and relationships, reconciles them over time, and makes them queryable through natural language, graph traversal, and structured query interfaces.

## Start Here

## Temporary documentation migration ledger

This section is a working transaction record for the clean-slate documentation
migration. It is intentionally temporary and will be removed once the actions
below are complete. The target documentation retains only current functional
and technical guidance; deprecated approaches are migrated where useful and
then deleted, not preserved as a legacy archive.

| Area | Current action | Target outcome |
| --- | --- | --- |
| `requirements/`, `network/`, `flows/`, `mvp/` | Retain functional product/domain material; refresh cross-links and remove superseded runtime detail. | One current product and domain specification. |
| `ai-engineering/` | Completed: focused files own AI contracts, runtime, states, providers, context, and prompt guidance; broad duplicate sources are removed. | One current AI contract and runtime specification. |
| `architecture/` | Completed: retain only the current system topology, component/lifecycle overview, and deterministic workflow coordination. | Only cross-component architecture remains; superseded agentic documents are deleted. |
| `external-integrations/` | Retain channel and media requirements; provider-runtime content is owned by `ai-engineering/providers/`. | Integration-specific documentation only. |
| `uat/` | Keep unchanged for now. | Deferred cleanup. |

Each child README records its local migration action. Do not delete a source
document until its retained concepts have an accepted canonical owner and its
inbound links have been updated.

- [Documentation conventions](documentation-conventions.md): required README,
  indexing, status, and DTO-first documentation rules.
- [Product foundation](requirements/product-foundation.md): vision, goals, non-goals, and core assumptions.
- [MVP baseline](mvp/baseline.md): practical first implementation target and architectural stance.
- [Project TODOs](todos.md): deferred follow-ups for provider smoke tests, rendering, tracing, UAT, and hardening.
- [AI engineering](ai-engineering/README.md): canonical contracts, runtime,
  providers, context, observability, and controlled migration documentation.
- [Functional capabilities](requirements/functional/core-capabilities.md): what the system must do from the user's point of view.
- [Frontend UI product requirements](requirements/ui/frontend-ui-product-requirements.md): product brief for chat, graph exploration, evidence, timeline, map, and analytics UI.
- [Technical principles](requirements/technical/technical-principles.md): engineering constraints and architecture principles.
- [Architecture overview](architecture/overview.md): major components and how they interact.
- [System architecture](architecture/system-architecture.md): consumers,
  application boundaries, external services, storage, and deployment posture.
- [Deterministic agentic workflows](architecture/deterministic-agentic-workflows.md):
  current ingestion-state sequencing and typed handoff contract.
- [Graph model](network/graph-model.md): entity types, relationship types, evidence, identity, and provenance.
- [Affective memory](network/affective-memory.md): emotional traits, perceptions, user voice, and subjective memory modeling.
- [Entity metadata and enrichment](network/entity-metadata-enrichment.md): contact details, external references, enrichment policy, and runtime lookup tradeoffs.
- [Metadata policy contract](network/metadata-policy-contract.md): how arbitrary metadata is accepted, promoted, indexed, and governed.
- [Memory lifecycle](network/memory-lifecycle.md): lifecycle states for preserving memories while handling stale, disputed, and corrected facts.
- [Temporal model](network/temporal-model.md): exact, fuzzy, observed, valid, and source time modeling.
- [Personal profile memory](network/personal-profile-memory.md): personality traits, preferences, stable user context, and LLM configuration memory.
- [Ingestion flow](flows/ingestion.md): conversational ingestion, clarification loops, extraction, and graph writes.
- [Entity resolution flow](flows/entity-resolution.md): duplicate prevention, ambiguous matches, merges, and splits.
- [Interrogation flow](flows/interrogation.md): Graph-RAG, natural language querying, graph queries, and answer grounding.
- [Memory maintenance and corrections](requirements/functional/memory-maintenance-and-corrections.md): future owner-facing correction, lifecycle, conflict, and merge/split behavior.
- [Privacy and trust](requirements/privacy-and-trust.md): privacy zones, trust levels, and answer behavior.
- [Telegram integration](external-integrations/telegram.md): first likely chat interface.
- [Media ingestion](external-integrations/media-ingestion.md): future handling of images, audio, documents, and other sources.

## Core Idea

The main output is a graph database of entities and relationships that represents memories and contextual knowledge. Entities include people, events, places, organizations, objects, media, topics, perceptions, relationship contexts, and other classes that become useful while modeling personal memory. Relationships capture facts such as participation, location, time, ownership, similarity, causality, references, and evidence.

The graph is built incrementally from conversations and other ingestion sources. A chat interface, most likely Telegram at first, lets the user send memories, notes, corrections, images, audio, or other inputs. An LLM-based ingestion pipeline extracts candidate entities, relationships, perceptions, emotional summaries for any memory target, user wording, and uncertainty, asks clarification questions when needed, and writes confirmed knowledge into the graph.

The graph is queried as a Graph-RAG system. It supports semantic search through embeddings, graph traversal, natural language questions, and structured SQL-like or graph-native queries. Retrieval must preserve the affective shape of memory: emotional summaries, subjective perceptions, relationship context, and original user wording should travel with the factual graph context for any relevant memory-bearing node or important relationship. The frontend will let the user visualize and navigate relevant graph neighborhoods rather than only reading generated answers.

## Documentation Map

| Area | Purpose |
| --- | --- |
| `requirements/` | Product, functional, and technical requirements. |
| `mvp/` | Practical first implementation scope and baseline decisions. |
| `ai-engineering/` | Canonical AI contracts, runtime, states, providers, context, prompts, and observability. |
| `architecture/` | System decomposition, data flow, component responsibilities, and future decisions. |
| `network/` | Graph schema, entity taxonomy, relation taxonomy, identity resolution, and provenance. |
| `flows/` | User and system workflows such as ingestion, clarification, querying, and visualization. |
| `external-integrations/` | Channel and media integrations; AI provider adapters are indexed under `ai-engineering/`. |

Every documentation directory has a `README.md` with its purpose and direct
index. See [Documentation conventions](documentation-conventions.md) for the
required maintenance rule.

## Decision ownership

This landing page indexes the project's sources of truth; it does not restate
their decisions. Product scope lives in
[Product foundation](requirements/product-foundation.md) and
[MVP baseline](mvp/baseline.md). System boundaries live in
[System architecture](architecture/system-architecture.md), AI behavior in
[AI engineering](ai-engineering/README.md), workflow order in
[Deterministic agentic workflows](architecture/deterministic-agentic-workflows.md),
and memory semantics in [Network documentation](network/README.md) and
[Functional requirements](requirements/functional/README.md).
