# MVP Baseline

## Purpose

This document captures the practical first implementation target. The project is personal-first, so the MVP should stay useful, agile, and simple instead of trying to become a complete public product platform.

## MVP Shape

The first version is a private backend container that manages a local graph database of personal memories and uses cloud or external AI services for model capabilities. Telegram is the first likely chat consumer, but a simple web chat must be able to act as a substitute over the same backend runtime.

High-level shape:

```text
Telegram Bot / Web Chat
  -> API and conversation entry
      -> AI Manager: capability workflows and AI runtime
          -> provider adapters: LLM / embeddings / speech-to-text
          -> memory network services
              -> Neo4j Graph Database
              -> Relational operational database
              -> Vector database
              -> source and media storage
```

## Core Flow

1. The user interacts through Telegram or web chat.
2. The chat consumer sends normalized text or voice inputs to the backend.
3. Voice messages are transcribed when speech-to-text is configured.
4. The AI Manager interprets the message as an ingestion, query, or other
   approved capability. An answer submitted through a clarification interaction
   is associated with its paused provider call and resumes that originating
   state.
5. The configured capability state interprets the input using bounded context
   and its approved tools.
6. The Network API performs graph CRUD, search, query, storage, statistics, and retrieval operations.
7. The AI Manager responds through Telegram or asks a clarification when useful.

## Architecture Stance

Semantic decisions inside states are agentic. Workflows schedule known
dependencies deterministically without attempting to model every conversational
branch upfront.

Principles:

- Keep the AI Manager responsible for conversational flow.
- Give the AI Manager tools to interact with the graph and sources.
- Keep graph writes validated and auditable.
- Persist a minimal paused continuation only while a configured tool awaits
  external input.
- Keep conversation history available for context building while keeping model-facing context scoped and low-noise.
- Keep durable chat history distinct from state-local/provider history; the
  centralized history session owns their state-run linkage.
- Render one final assistant message by default. Activity and clarification
  packets support UI interaction without becoming chat content or a generic
  sidecar protocol.
- Let edge cases exist until they are common or harmful enough to justify explicit handling.
- Prefer useful memory capture over complete process coverage.

## Clarification Stance

Clarification is part of the AI Manager ingestion loop. It is not a standalone public API or heavy workflow engine.

MVP behavior:

- If a configured state needs clarification, its provider tool call pauses.
- The backend persists the minimum typed continuation needed to resume that
  state and expires an abandoned continuation under the approved retention
  policy.
- The submitted answer becomes the one matching tool output for the open call.
- The same originating state resumes with its preserved history, typed context,
  and model-facing references.
- An unrelated new conversation request does not pass through a generic
  pending-process router.

Minimal persisted state:

- `conversation_id`
- `state_run_id` and parent linkage when applicable
- opaque channel interaction association
- the open provider-call association
- typed state context and local-history reference
- `expires_at`
- `updated_at`

This is state for continuation, not a separate clarification subsystem or rigid
workflow engine.

## Chat Runtime Baseline

Chat runtime state should be channel-neutral.

Baseline decisions:

- Telegram and web chat both map into internal `ChatSession` and `ConversationMessage` records.
- Chat messages/history are stored separately from chat session state.
- State-local/provider history is separate from visible chat history and is
  linked through the centralized history service.
- A completed interaction renders one final user-facing assistant message.
- Activity events and clarification packets are separate operational UI data;
  evidence is exposed only where it is useful to the user.
- Telegram and web chat render the same semantic interaction in channel-
  appropriate forms.
- MVP web chat uses a static bearer token, not a full user account system.

## Agent Tools

Conversation entry exposes a deliberately small top-level tool surface:
`query_memory` and `ingest_memory`. Child states receive only their configured
toolboxes. `ask_clarification` is available only where a state can pause for
external input; deterministic graph tools remain state-specific and auditable.

## Technology Direction

Preferred starting point:

- Python backend.
- FastAPI or similar lightweight Python API framework.
- Pydantic or equivalent for structured objects.
- Neo4j graph database.
- Relational operational database from v1, local or remote.
- Separate vector database from v1, with Chroma locally and Azure AI services in cloud mode through a protocolled interface.
- Local source/media storage for MVP.
- OpenAI or Azure OpenAI for LLM usage.
- Speech-to-text provider configurable for voice messages.
- Frontend later, likely React, Next.js, or similar.

This is a baseline, not a lock-in. Choices can evolve as implementation pressure appears.

## What To Keep Agile

- Exact frontend stack.
- Exact JSON contracts beyond first coding needs.
- Complete edge-case handling.
- Advanced media ingestion beyond voice transcription.
- Public-product concerns.

## What Should Not Be Deferred

- Source provenance.
- Graph write validation.
- Neo4j as graph database.
- Relational operational storage.
- Vector store protocol.
- LLM-facing ID aliases for model contexts.
- Minimal paused-state continuation.
- Voice transcript provenance.
- Entity resolution basics.
- Local/cloud-friendly configuration.
- Privacy-aware provider boundaries.
