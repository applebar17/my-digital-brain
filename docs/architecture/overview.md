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
  |----> Neo4j Graph Database
  |----> Relational Operational Database
  |----> Vector Database
  |----> Source / Media Storage
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

The target runtime model for this layer is defined in [Agentic tool frame runtime](agentic-tool-frame-runtime.md). Agentic behavior should be modeled as purpose-oriented frames with explicit prompts, context packages, allowed tools, forbidden tools, output schemas, and provider tool-call continuations.

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

The Network API also owns ID translation for model contexts. Internal persistent UUIDs can be mapped to short LLM-facing aliases such as `NODE_000001` and resolved back before any graph operation.

### Source And Evidence Store

Preserves raw inputs, metadata, transcripts, attachments, and user confirmations. The graph should reference this store instead of copying every raw artifact into graph properties.

### Relational Operational Store

Stores application runtime data that should not live directly in the graph, such as Telegram chat records, pending ingestion sessions, provider request logs, job state, prompt/schema registries, vector record references, backup/export records, and audit logs.

The relational store can be local or remote. It supports the application, but the graph remains the canonical memory model.

### Vector Store

Stores embeddings for semantic retrieval. The application should access it through a protocolled interface, with Chroma as the local option and Azure AI services as the cloud option.

The vector store is a semantic lookup index, not the source of truth for
memories. Vector records must point back to Neo4j graph targets and relational
vector record metadata. Retrieval must hydrate Chroma hits through Neo4j before
answer generation. Detailed implementation decisions are defined in
[Graph-RAG and vector retrieval implementation plan](../dev-plans/09-graph-rag-and-vector-retrieval.md).

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
- One Neo4j graph database.
- One relational operational database.
- One vector database.
- One source/evidence store.
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
- Local vector database, initially Chroma.
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
- Cloud vector store through Azure AI services.
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

- Exact relational database implementation.
- Exact vector store implementation details behind the `VectorStore` protocol.
- LLM provider and model strategy.
- Queue/background worker technology.
- Authentication and user identity model.
- Exact AI Manager tool surface.
- Exact Network API surface.
- Local, hosted, hybrid, and future public-product deployment boundaries.
- Backup, export, and deletion model.
