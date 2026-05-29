# Backend Chat Interface And DB Tooling

## Goal

Define the Telegram chatbot, AI Manager behavior, and Network API tooling that let the user store memories, retrieve memories, and interact with the graph.

## Wave 0: Baseline Decisions

- Telegram is the first chat interface.
- Telegram integration belongs in this plan, not in the generic external integrations plan.
- The AI Manager owns conversational behavior.
- The Network API owns graph CRUD, query, search, statistics, and retrieval context.
- Clarification is handled inside the AI Manager loop with minimal pending state.
- The bot should feel conversational, not like a form or admin console.

## Wave 1: MVP Chat Interface

Telegram capabilities:

- Receive text messages.
- Receive voice messages.
- Normalize Telegram updates into internal source records.
- Download or reference Telegram voice artifacts.
- Send ingestion summaries.
- Ask clarification questions.
- Answer natural language memory questions.
- Handle minimal commands such as `/remember`, `/ask`, `/status`, `/cancel`, and `/help`.

AI Manager capabilities:

- Detect intent: ingest memory, answer query, clarification answer, correction, or tool request.
- Build context for each step.
- Select model based on task difficulty when configured.
- Call Network API tools.
- Keep pending ingestion state minimal and expiring.
- Route text and voice inputs to the ingestion pipeline.

Network API capabilities:

- Create/update entities.
- Create/update relationships.
- Store sources.
- Link evidence.
- Query entities and relationships.
- Retrieve graph context.
- Search by name, alias, type, time, and source.

## Wave 2: Rich Query And Memory Tools

- Graph-RAG retrieval flow for natural language questions.
- Explain retrieved evidence when useful.
- Query current versus historical facts.
- Retrieve latest contact details.
- Retrieve memories by place, person, topic, or time.
- Add correction tools for wrong facts, stale values, and duplicate entities.
- Add contradiction notification through Telegram.

## Wave 3: Advanced Agentic Tooling

- Tool for graph statistics.
- Tool for graph neighborhood summaries.
- Tool for timeline extraction.
- Tool for map result extraction.
- Tool for profile memory inspection.
- Tool for enrichment lookup.
- Tool for memory maintenance suggestions.

## Tooling Principles

- Tool descriptions must be clear because they are prompt surface.
- Tool inputs should use Pydantic schemas.
- Tools that mutate graph state must be auditable.
- Risky tools require confirmation.
- The AI Manager can be dynamic, but the tool layer should be stable.

## Initial Success Criteria

- The user can store a memory via Telegram.
- The user can store a memory via voice message.
- Telegram updates are isolated behind a small adapter so the AI Manager does not depend on raw Telegram payloads.
- The user can ask a question and get a grounded answer.
- The bot can ask and resume one clarification.
- The Network API can be used independently for graph CRUD and query operations.
