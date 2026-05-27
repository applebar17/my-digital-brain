# My Digital Brain Documentation

This documentation describes the foundation for a personal digital brain: a graph-based memory system that ingests user-provided information, extracts entities and relationships, reconciles them over time, and makes them queryable through natural language, graph traversal, and structured query interfaces.

## Start Here

- [Product foundation](requirements/product-foundation.md): vision, goals, non-goals, and core assumptions.
- [MVP baseline](mvp/baseline.md): practical first implementation target and architectural stance.
- [Functional capabilities](requirements/functional/core-capabilities.md): what the system must do from the user's point of view.
- [Technical principles](requirements/technical/technical-principles.md): engineering constraints and architecture principles.
- [Architecture overview](architecture/overview.md): major components and how they interact.
- [Graph model](network/graph-model.md): entity types, relationship types, evidence, identity, and provenance.
- [Entity metadata and enrichment](network/entity-metadata-enrichment.md): contact details, external references, enrichment policy, and runtime lookup tradeoffs.
- [Metadata policy contract](network/metadata-policy-contract.md): how arbitrary metadata is accepted, promoted, indexed, and governed.
- [Memory lifecycle](network/memory-lifecycle.md): lifecycle states for preserving memories while handling stale, disputed, and corrected facts.
- [Temporal model](network/temporal-model.md): exact, fuzzy, observed, valid, and source time modeling.
- [Personal profile memory](network/personal-profile-memory.md): personality traits, preferences, stable user context, and LLM configuration memory.
- [Ingestion flow](flows/ingestion.md): conversational ingestion, clarification loops, extraction, and graph writes.
- [Structured ingestion objects](flows/structured-ingestion-objects.md): candidate entities, relationships, claims, metadata patches, and validation objects.
- [Entity resolution flow](flows/entity-resolution.md): duplicate prevention, ambiguous matches, merges, and splits.
- [Interrogation flow](flows/interrogation.md): Graph-RAG, natural language querying, graph queries, and answer grounding.
- [Memory management agent](flows/memory-management-agent.md): simple agent/toolbox for corrections, contradictions, and maintenance.
- [Privacy and trust](requirements/privacy-and-trust.md): privacy zones, trust levels, and answer behavior.
- [Telegram integration](external-integrations/telegram.md): first likely chat interface.
- [LLM integration](external-integrations/llm-integration.md): how models are used for extraction, clarification, resolution, and querying.
- [Media ingestion](external-integrations/media-ingestion.md): future handling of images, audio, documents, and other sources.

## Core Idea

The main output is a graph database of entities and relationships that represents memories and contextual knowledge. Entities include people, events, places, organizations, objects, media, topics, and other classes that become useful while modeling personal memory. Relationships capture facts such as participation, location, time, ownership, similarity, causality, references, and evidence.

The graph is built incrementally from conversations and other ingestion sources. A chat interface, most likely Telegram at first, lets the user send memories, notes, corrections, images, audio, or other inputs. An LLM-based ingestion pipeline extracts candidate entities and relationships, detects uncertainty, asks clarification questions when needed, and writes confirmed knowledge into the graph.

The graph is queried as a Graph-RAG system. It supports semantic search through embeddings, graph traversal, natural language questions, and structured SQL-like or graph-native queries. The frontend will let the user visualize and navigate relevant graph neighborhoods rather than only reading generated answers.

## Documentation Map

| Area | Purpose |
| --- | --- |
| `requirements/` | Product, functional, and technical requirements. |
| `mvp/` | Practical first implementation scope and baseline decisions. |
| `architecture/` | System decomposition, data flow, component responsibilities, and future decisions. |
| `network/` | Graph schema, entity taxonomy, relation taxonomy, identity resolution, and provenance. |
| `flows/` | User and system workflows such as ingestion, clarification, querying, and visualization. |
| `external-integrations/` | Interfaces with Telegram, LLM providers, media processors, and future data sources. |

## Current Baseline Decisions

- The graph is the canonical memory store.
- The first target user is the owner of the brain, not a public multi-user SaaS product.
- The MVP is a Telegram-based backend container managing a local graph database and using cloud/external AI services.
- The backend should be split conceptually between an AI Manager layer and a Network API layer.
- Every extracted fact should retain provenance back to the source message, media item, or user confirmation.
- LLM output is treated as a proposal until validated by rules, confidence thresholds, user clarification, or explicit confirmation.
- Structured ingestion objects are required between LLM extraction and graph writes.
- Duplicate handling and entity unification are first-class requirements, not cleanup tasks.
- Sensitive and mutable metadata, such as contact details, should be modeled with provenance and validity rather than buried in arbitrary metadata.
- Memory lifecycle should preserve memories by default while still allowing correction, dispute, expiration, and deletion.
- Time must be modeled explicitly, including fuzzy time, valid time, observed time, and source time.
- Clarification is an agentic ingestion behavior, not a standalone workflow engine or public API.
- Ambiguity should trigger clarification where useful, especially for people, locations, dates, and event boundaries.
- Contradictions should trigger a friendly clarification path when they matter.
- Natural language answers must be grounded in retrieved graph facts and source evidence.
- The architecture should support both local-first and cloud deployment modes.
- Voice-message ingestion should be supported early through configurable speech-to-text.
- Richer media ingestion is part of the roadmap, but text and voice conversational ingestion are the first practical paths.

## Open Decisions

- Graph database: Neo4j, Memgraph, ArangoDB, PostgreSQL with graph extensions, or another option.
- Query language: Cypher, Gremlin, SQL over graph tables, or a custom query abstraction.
- Embedding storage: inside the graph database, in a vector database, or in PostgreSQL.
- LLM provider strategy: single provider first, or provider abstraction from day one.
- Confirmation policy: what can be auto-written versus what requires user confirmation.
- Final deployment mode: fully local, private cloud, hybrid, or public product later.
