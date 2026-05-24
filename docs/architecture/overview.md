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
Source Store ---> LLM Extraction ---> Clarification Manager
  |                  |                       |
  |                  v                       v
  |            Candidate Graph        User Clarifications
  |                  |
  v                  v
Evidence Store --> Resolution Engine --> Graph Writer
                     |                |
                     v                v
          Personal Profile Agent   Graph Database
                                      |
                                      v
                           Retrieval + Query Layer
                                      |
                                      v
                         Chat Answers + Graph UI
```

## Component Responsibilities

### Ingestion Interfaces

Receive input from Telegram, the frontend, and future external services. They normalize text messages, voice messages, and other media into source records.

### Source And Evidence Store

Preserves raw inputs, metadata, transcripts, attachments, and user confirmations. The graph should reference this store instead of copying every raw artifact into graph properties.

### LLM Extraction

Converts source records into candidate entities, candidate relationships, summaries, missing-field signals, and ambiguity signals.

### Media Processing

Processes media sources into derived artifacts. For the early product, the most important media process is speech-to-text transcription for voice messages. The transcript then enters the normal ingestion flow while preserving a link back to the original audio.

### Clarification Manager

Tracks incomplete ingestion sessions and asks the user targeted follow-up questions. It merges clarification answers back into the candidate graph before final resolution.

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

- One backend service for ingestion, resolution, querying, and API endpoints.
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
4. Extraction creates candidate entities and relationships from text or transcript.
5. Validation checks structure and confidence.
6. Clarification is requested if required.
7. Resolution compares candidates with existing graph state.
8. Graph writes create or update entities, relationships, evidence links, and embeddings.
9. Durable user traits are routed to the personal profile agent when detected.
10. Retrieval uses the graph, embeddings, and approved profile memory to answer questions or power visualization.

## Architecture Decisions To Make

- Graph database selection.
- Embedding storage strategy.
- LLM provider and model strategy.
- Queue/background worker technology.
- Authentication and user identity model.
- Local, hosted, hybrid, and future public-product deployment boundaries.
- Backup, export, and deletion model.
