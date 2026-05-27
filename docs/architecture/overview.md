# Architecture Overview

## High-Level Components

```text
User
  |
  v
Chat Interface / Frontend / External Sources
  |
  v
Ingestion API
  |
  v
AI Manager
  |
  |----> Model Providers / Speech-to-Text / External Tools
  |
  |----> Source Store / Evidence Store / Media Processing
  |
  v
Network API
  |
  |----> Entity + Relationship CRUD
  |----> Graph Query + Search
  |----> Resolution + Contradiction Checks
  |----> Statistics + Retrieval Context
  |
  v
Graph Database
  |
  v
Chat Answers + Graph UI
```

## Component Responsibilities

### Ingestion Interfaces

Receive input from Telegram, the frontend, and future external services. They normalize text messages, voice messages, and other media into source records.

### AI Manager

Owns the agentic behavior of the system. It decides whether an incoming message is a new memory, a query, a clarification answer, a correction, or a tool-driven operation.

The AI Manager coordinates model calls, speech-to-text, source storage, extraction, clarification, resolution, and calls to the Network API. It should remain dynamic and tool-driven rather than fully deterministic.

### Network API

Provides the stable interface to the memory network and graph database.

Responsibilities:

- Entity CRUD.
- Relationship CRUD.
- Claim and metadata storage.
- Source and evidence linking.
- Graph queries.
- Retrieval context assembly.
- Entity resolution support.
- Contradiction checks.
- Statistics and diagnostics.

The Network API should validate graph writes and keep them auditable. The AI Manager can be dynamic, but graph mutations should still be structured.

### Source And Evidence Store

Preserves raw inputs, metadata, transcripts, attachments, and user confirmations. The graph should reference this store instead of copying every raw artifact into graph properties.

### LLM Extraction

Converts source records into candidate entities, candidate relationships, summaries, missing-field signals, and ambiguity signals.

### Media Processing

Processes media sources into derived artifacts. For the early product, the most important media process is speech-to-text transcription for voice messages. The transcript then enters the normal ingestion flow while preserving a link back to the original audio.

### Clarification Handling

Clarification is part of the AI Manager ingestion loop, not a standalone public API or heavy workflow engine. The MVP only needs enough persisted state to resume the latest pending ingestion for a Telegram chat and expire it when it is no longer relevant.

### Resolution Engine

Matches candidate entities and relationships against the existing graph. It decides whether to reuse, merge, create, reject, or ask for clarification.

### Personal Profile Agent

Detects durable information about the owner of the brain, such as personality traits, preferences, communication style, stable goals, dislikes, habits, and important self-descriptions. It writes these as profile memory proposals, not as unreviewed prompt instructions.

### Graph Writer

Applies validated changes to the graph database. It should be deterministic, auditable, and idempotent.

### Retrieval And Query Layer

Supports Graph-RAG, semantic search, graph traversal, structured queries, and answer grounding.

### Frontend

Provides search, graph visualization, entity inspection, evidence inspection, and later correction workflows.

## Suggested Initial Runtime Shape

The first practical implementation can be modular without being over-distributed:

- One backend service containing the AI Manager and Network API layers.
- One graph database.
- One source/evidence store.
- One embedding store, either integrated with the database or separate.
- One Telegram bot integration.
- One web frontend.
- Background jobs for extraction, voice transcription, media processing, embeddings, and graph maintenance.

This keeps the system understandable while preserving clear boundaries for later scaling.

## Deployment Modes

The architecture should support both local-friendly and cloud-friendly deployment.

### Local-Friendly Mode

Local mode is optimized for personal privacy, experimentation, and offline-friendly development.

Expected shape:

- Docker Compose or equivalent local container orchestration.
- Backend service running locally.
- Local graph database.
- Local Postgres or lightweight source store.
- Local file/object storage for media.
- Optional local LLM and embedding models.
- Optional local chat interface when Telegram is not desired.

Local mode should be able to run without exposing a public webhook. Telegram can still be supported through polling, tunnels, or an optional cloud relay, but the core system should not depend on public hosting.

### Cloud-Friendly Mode

Cloud mode is optimized for reliable availability and external integrations.

Expected shape:

- Hosted backend service.
- Managed or self-hosted graph database.
- Managed Postgres or equivalent operational store.
- Object storage for media.
- Queue and background workers.
- Telegram webhook endpoint.
- Cloud LLM providers, local models, or a hybrid provider strategy.

### Public Product Later

The first version is personal-first. Public-product requirements such as multi-tenancy, billing, onboarding, plan limits, and customer support should not drive the early architecture, but the system should avoid choices that make those impossible later.

## Data Lifecycle

1. A source is received from a text message, voice message, or another ingestion channel.
2. The raw source is stored with metadata.
3. Voice messages are transcribed and stored as derived source artifacts.
4. The AI Manager decides whether the input starts a new process or resumes a pending one.
5. Extraction creates candidate entities and relationships from text or transcript.
6. Validation checks structure and confidence.
7. Clarification is requested by the AI Manager if useful.
8. Resolution compares candidates with existing graph state through the Network API.
9. Graph writes create or update entities, relationships, evidence links, and embeddings.
10. Durable user traits are routed to the personal profile agent when detected.
11. Retrieval uses the graph, embeddings, and approved profile memory to answer questions or power visualization.

## Architecture Decisions To Make

- Graph database selection.
- Embedding storage strategy.
- LLM provider and model strategy.
- Queue/background worker technology.
- Authentication and user identity model.
- Exact AI Manager tool surface.
- Exact Network API surface.
- Local, hosted, hybrid, and future public-product deployment boundaries.
- Backup, export, and deletion model.
