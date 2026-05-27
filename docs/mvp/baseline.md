# MVP Baseline

## Purpose

This document captures the practical first implementation target. The project is personal-first, so the MVP should stay useful, agile, and simple instead of trying to become a complete public product platform.

## MVP Shape

The first version is a Telegram-based backend container that manages a local graph database of personal memories and uses cloud or external AI services for model capabilities.

High-level shape:

```text
Telegram Bot
  -> AI Manager
      -> OpenAI / Azure OpenAI / speech-to-text / tools
      -> Network API
          -> Graph Database
          -> source and media storage
```

## Core Flow

1. The user interacts with a Telegram chatbot.
2. The bot sends text or voice inputs to the backend.
3. Voice messages are transcribed when speech-to-text is configured.
4. The AI Manager decides whether the input is a memory ingestion, clarification answer, query, correction, or tool request.
5. The AI Manager extracts candidate graph updates or query plans.
6. The Network API performs graph CRUD, search, query, storage, statistics, and retrieval operations.
7. The AI Manager responds through Telegram or asks a clarification when useful.

## Architecture Stance

The MVP should be agentic and dynamic. It should not try to deterministically model every possible conversational branch upfront.

Principles:

- Keep the AI Manager responsible for conversational flow.
- Give the AI Manager tools to interact with the graph and sources.
- Keep graph writes validated and auditable.
- Persist only the minimal state needed to resume pending work.
- Let edge cases exist until they are common or harmful enough to justify explicit handling.
- Prefer useful memory capture over complete process coverage.

## Clarification Stance

Clarification is part of the AI Manager ingestion loop. It is not a standalone public API or heavy workflow engine.

MVP behavior:

- If an ingestion needs clarification, mark the latest ingestion session for that Telegram chat as waiting.
- The next user message in that chat is treated as the clarification answer unless the AI Manager decides otherwise.
- The answer is appended to the pending ingestion session.
- The AI Manager resumes extraction, resolution, and graph update.
- Pending sessions have expiration.

Minimal persisted state:

- `ingestion_session_id`
- `telegram_chat_id`
- `status`
- `pending_question`
- `candidate_graph_snapshot`
- `expires_at`
- `updated_at`

This is state for continuity, not a separate clarification subsystem.

## Agent Tools

The AI Manager can eventually use tools such as:

- `ingest_text`
- `ingest_voice_transcript`
- `resume_pending_ingestion`
- `restart_process`
- `skip_clarification`
- `expire_pending_process`
- `query_graph`
- `create_or_update_entity`
- `create_or_update_relationship`
- `detect_contradictions`
- `ask_user_clarification`
- `store_source`
- `get_entity_context`

Tools should be auditable when they change graph state.

## Technology Direction

Preferred starting point:

- Python backend.
- FastAPI or similar lightweight Python API framework.
- Pydantic or equivalent for structured objects.
- Local graph database, likely Neo4j unless a better reason emerges.
- Local source/media storage for MVP.
- OpenAI or Azure OpenAI for LLM usage.
- Speech-to-text provider configurable for voice messages.
- Frontend later, likely React, Next.js, or similar.

This is a baseline, not a lock-in. Choices can evolve as implementation pressure appears.

## What To Keep Agile

- Exact frontend stack.
- Exact graph database until implementation starts.
- Exact JSON contracts beyond first coding needs.
- Complete edge-case handling.
- Advanced media ingestion beyond voice transcription.
- Public-product concerns.

## What Should Not Be Deferred

- Source provenance.
- Graph write validation.
- Minimal pending ingestion state.
- Voice transcript provenance.
- Entity resolution basics.
- Local/cloud-friendly configuration.
- Privacy-aware provider boundaries.
