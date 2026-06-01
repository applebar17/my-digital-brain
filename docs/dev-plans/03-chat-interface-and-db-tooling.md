# Chat Consumers, Conversation Runtime, And Backend Tool Facade

## Goal

Build the chat-facing runtime that lets the user interact with the digital brain through multiple chat consumers.

Telegram is one consumer. A simple web chat frontend must be a first-class substitute, not a secondary admin surface. Both channels should normalize messages into the same backend contracts and call the same conversation runtime.

This plan wires chat inputs to backend capabilities and storage. It does not fully design the agentic behavior of every process and subprocess. Agent capabilities, toolboxes, behavioral protocols, prompt strategy, and nested process logic require a dedicated agentic-process design track.

## Expected Output

This plan should produce integration building blocks:

```text
Telegram chat        Web chat frontend
      |                    |
      v                    v
Chat consumer adapters and normalizers
      |
      v
Conversation runtime
sessions, conversation history, pending process context, response formatting
      |
      v
Backend tool facade
start ingestion, query memory context, propose correction
      |
      v
Existing backend services
ingestion, graph, AI provider, storage, vector store later
```

By the end of this plan:

- A user can send text through Telegram or web chat.
- A user can send voice/audio through Telegram or web chat when supported by the channel.
- Chat inputs become normalized backend messages.
- Normalized messages can start ingestion, query memory context, or propose corrections through a stable backend facade.
- Pending process context can be stored, attached to later messages, resumed when appropriate, cancelled, and expired.
- Telegram and web chat remain thin adapters with no memory business logic.
- The tool facade mirrors backend service capabilities without exposing raw graph CRUD or arbitrary database access.

## Locked Architecture Decisions

- Chat channels are adapters, not business logic owners.
- Telegram and web chat must call the same backend runtime.
- The conversation runtime owns channel-neutral message handling, conversation history references, lightweight session state, pending process context, and response shaping.
- Pending process state is context, not a rigid workflow route. It must help the runtime or future agents resume work when useful without forcing the next user message into a form-like path.
- A pending clarification should not automatically consume the next message. The next message should be handled with the pending context attached so runtime or agent configuration can classify it as clarification answer, new memory, question, cancellation, correction, or normal chat.
- The ingestion package owns memory ingestion business logic.
- The graph services own graph reads, graph writes, context packages, timelines, views, and analytics.
- The AI provider layer owns model calls, routing, speech-to-text, and provider abstraction.
- The backend tool facade wraps existing services into stable callable operations.
- The LLM never writes directly to graph, relational storage, files, or vector stores.
- The top-level conversational action surface remains intentionally small:
  - default answer path: no tool
  - `start_memory_ingestion`
  - `query_memory_context`
  - `propose_memory_correction`
- Resume, cancel, expire, validation, write-plan execution, and session persistence are backend process operations. They may be callable by the runtime, but they are not broad agent tools.
- Full agentic behavior design is out of scope for this plan and should be handled separately.

## Locked Implementation Decisions

### Session Model

Chat sessions are channel-neutral. Telegram chats and web chat sessions map into the same internal session contract.

Recommended session fields:

- `session_id`
- `channel`: `telegram` or `web`
- `external_conversation_id`
- `owner_id`
- `status`: `active` or `archived`
- `active_pending_process_id`
- `last_message_at`
- `created_at`
- `updated_at`
- `metadata`

Conversation messages are stored separately from session state.

Recommended message fields:

- `message_id`
- `session_id`
- `channel_message_id`
- `role`: `user`, `assistant`, or `system`
- `text`
- `media_refs`
- `source_ref`
- `pending_process_id`
- `created_at`
- `metadata`

Impact:

- Chat history can be used for context building without bloating the session record.
- Telegram and web chat remain equivalent.
- Pending process state can be linked without making chat sessions ingestion-specific.

### Response Shape And Rendering

Use one primary assistant message by default. Do not model normal chat replies as a list of visible response parts.

Recommended response fields:

- `response_id`
- `session_id`
- `status`
- `primary_text`
- `pending_process`
- `actions`
- `evidence`
- `diagnostics`
- `metadata`

Rendering policy:

- Telegram renders `primary_text` as one message in the normal case.
- Web chat renders `primary_text` as the main assistant message and may optionally render `actions`, `evidence`, or status as UI affordances.
- Multiple visible messages are only used when explicitly requested by the response, for example a long answer plus an evidence summary.
- Clarification requests are normal assistant messages with pending process metadata attached.
- Diagnostics are for tooling, debug, and verbose error handling; they are not normally user-visible.

Impact:

- The chat remains natural and low-friction.
- The backend still has enough structure for pending processes, web UI actions, evidence display, and future agent recovery.
- Telegram integration stays simple.

### Session Persistence

The initial runtime implementation should define a `ChatSessionStore` protocol and start with an in-memory implementation for local development and unit tests.

Relational persistence should follow the same interface and is required before relying on deployed Telegram webhooks, because webhook processes can restart.

Impact:

- The runtime can be implemented and tested without a database migration blocker.
- Durable storage can be added without changing runtime behavior.

### Web Chat Authentication

The MVP web chat should use a static bearer token:

```text
Authorization: Bearer <token>
```

This is not a full user system. It is a private-project guardrail so local or private deployments do not expose personal memories by accident.

Impact:

- Low implementation cost.
- Enough protection for a personal MVP.
- Can be replaced by proper authentication later.

### Chat Sessions And Ingestion Sessions

Do not merge chat sessions and ingestion sessions.

- `ChatSession` owns conversation/message runtime state.
- `IngestionSession` owns memory-ingestion process state.
- They are linked by `active_pending_process_id` or message-level `pending_process_id`.

Impact:

- Chat UX remains separate from ingestion business logic.
- Query and correction processes can reuse the same chat runtime later.
- A pending ingestion can be resumed without forcing the next chat message to be interpreted as the clarification answer.

## Relationship To Existing Work

### Uses The Ingestion Pipeline

The chat runtime should call the ingestion services defined in [backend ingestion pipeline](02-backend-ingestion-pipeline.md).

The chat runtime must not reproduce ingestion logic. It should pass normalized source inputs into ingestion and handle returned states:

- `candidate_ready`
- `needs_clarification`
- `write_plan_ready`
- `written`
- `validation_failed`
- `failed`

### Uses The AI Provider Foundation

Voice/audio messages should be transcribed through the AI provider layer. The transcript then enters the same ingestion path as typed text.

The chat runtime should not call provider SDKs directly unless it is invoking the provider abstraction.

### Uses The Graph Foundation

Query and answer flows should use graph query/context services and LLM-ready context packages. Raw Cypher and arbitrary graph CRUD are not exposed to the conversational layer.

## Explicit Non-Goal: Full Agentic Process Design

This plan creates the runtime and tool facade needed by future agents. It does not define all agent behavior.

Separate agentic-process design should cover:

- Conversation router behavior.
- Memory ingestion agent/process behavior.
- Clarification manager behavior.
- Memory query process behavior.
- Correction process behavior.
- Contradiction judge behavior.
- Profile/personality memory process behavior.
- Toolboxes per process and subprocess.
- Prompt protocols.
- Model routing by difficulty.
- Retry and fallback policies.
- Privacy and confirmation rules.
- Evaluation examples.

The distinction matters:

- This plan answers: how do chat messages reach backend services?
- Agentic-process design answers: how should agents reason, choose tools, ask questions, and coordinate subprocesses?

## Core Components

### Chat Message Contracts

Create channel-neutral contracts for:

- normalized incoming text message
- normalized incoming audio/voice message
- normalized attachment reference
- outgoing chat response
- pending process reference
- pending process context
- conversation/session state
- conversation history item/reference
- channel metadata

Expected fields:

- `channel`: `telegram` or `web`
- `conversation_id`
- `sender_id`
- `owner_id`
- `message_id`
- `text`
- `media_refs`
- `reply_to_message_id`
- `pending_process_id`
- `conversation_history_refs`
- `received_at`
- `metadata`

These contracts are transport contracts, not memory extraction contracts.

`ChatResponse` should use `primary_text` as the normal visible assistant message. Structured sidecars such as `pending_process`, `actions`, `evidence`, and `diagnostics` support runtime behavior and richer web UI rendering without fragmenting the chat into mechanical message parts.

### Chat Consumer Adapters

Adapters translate channel-specific payloads into normalized chat messages.

Telegram adapter responsibilities:

- Receive Telegram updates.
- Normalize text messages.
- Normalize voice/audio messages.
- Download or reference voice artifacts.
- Send text responses.
- Send clarification questions.
- Send status/failure responses.
- Keep Telegram payload details outside the conversation runtime.

Web chat adapter responsibilities:

- Expose backend API endpoints for web chat messages.
- Support text messages.
- Support audio upload or recorded audio when implemented.
- Return frontend-friendly response payloads.
- Display pending clarification prompts and process status when provided by the backend.
- Avoid memory business logic in frontend code.

Future mobile or desktop clients should reuse the same normalized contracts.

### Conversation Runtime

The conversation runtime coordinates channel-neutral message handling.

Responsibilities:

- Receive normalized messages from adapters.
- Store or reference source input before processing.
- Store conversation history references for context building.
- Load and attach pending process context when present.
- Let runtime configuration or later agentic process design classify the message as a clarification answer, new memory, question, cancellation, correction, or normal chat.
- Call the backend tool facade.
- Return channel-neutral response objects.
- Keep session state minimal and expiring.
- Avoid rigid form-like flows that block natural conversation.
- Avoid direct graph writes.
- Avoid direct provider SDK calls.

The runtime can be deterministic at first. Rich intent routing through an LLM belongs to the agentic-process design track.

### Backend Tool Facade

The facade exposes stable backend operations to the chat runtime and future agents.

Initial operations:

- `start_memory_ingestion`
- `query_memory_context`
- `propose_memory_correction`

Runtime-only operations:

- `get_conversation_status`
- `cancel_pending_process`
- `resume_pending_process`
- `expire_pending_sessions`

Runtime-only operations are backend process controls. They should not be treated as broad top-level agent tools unless a later agentic design explicitly allows it.

Tool facade rules:

- Use Pydantic schemas.
- Keep descriptions clear because they are prompt surface.
- Return structured success, clarification, validation failure, or execution failure results.
- Never expose arbitrary Cypher.
- Never expose raw database CRUD to the conversational model.
- Mutating operations must be auditable.
- Risky correction operations require confirmation.

## Tool Facade Baseline

### `start_memory_ingestion`

Purpose:

Start ingestion from a normalized text source or transcript source.

Inputs:

- source text or transcript id
- channel
- conversation id
- source/media references
- optional pending process context
- optional conversation history references

Outputs:

- ingestion status
- summary for the user
- clarification question when needed
- validation errors when extraction or write-plan validation fails
- write result when execution succeeds

Backend services used:

- source storage/process store
- ingestion service
- AI provider for structured extraction when configured
- graph service through validated write plans

### `query_memory_context`

Purpose:

Retrieve graph context for answering a natural language memory question.

Inputs:

- user question
- conversation id
- optional known seed refs
- optional time/place/person hints
- limit and privacy settings

Outputs:

- low-noise context package
- graph node aliases
- relevant relationships
- timeline snippets
- source/evidence summaries
- answer-ready payload

Backend services used:

- graph search/query services
- graph context packages
- vector retrieval later
- AI answer generation later

### `propose_memory_correction`

Purpose:

Capture a user correction and turn it into a safe backend correction process.

Inputs:

- correction text
- target aliases or target hints
- source/evidence reference
- confirmation flag when required

Outputs:

- correction proposal
- required clarification or confirmation
- applied result when safe and confirmed

Backend services used:

- graph query services
- lifecycle/change-record services
- ingestion/correction-specific services later

Correction behavior needs dedicated design before aggressive mutation is allowed.

## Wave 0: Locked Scope

- This plan wires chat consumers to backend services.
- Telegram and web chat are equal first-class consumers.
- Agentic process behavior is not fully designed here.
- The web chat surface is a product interface, not just a developer debug console.
- The backend tool facade mirrors service capabilities through stable, narrow operations.
- Pending process state must stay lean and contextual. It supports resumption and expiry, but does not own a strict deterministic conversation flow.
- Tool exposure to agents and subprocesses requires separate discussion.

## Wave 1: Channel-Neutral Chat Runtime

Status: implemented in `src/my_digital_brain/chat/` with API routes in `src/my_digital_brain/api/routes/chat.py` and unit/API coverage in `tests/test_chat_runtime.py`.

### Summary

Create the shared chat contracts, conversation runtime, session store interface, and tool facade skeleton.

### Key Changes

- Add chat package, for example `src/my_digital_brain/chat/`.
- Add contracts for:
  - `ChatChannel`
  - `IncomingChatMessage`
  - `IncomingMediaRef`
  - `ChatResponse`
  - `ChatAction`
  - `ChatEvidenceRef`
  - `ChatDiagnostic`
  - `ConversationSession`
  - `ConversationMessage`
  - `PendingProcessRef`
  - `PendingProcessContext`
  - `ConversationHistoryItem`
- Add conversation runtime service:
  - receive normalized messages
  - store conversation history references
  - attach pending process context when present
  - call tool facade operations
  - return channel-neutral responses
- Add tool facade skeleton:
  - `start_memory_ingestion`
  - `query_memory_context`
  - `propose_memory_correction`
- Add minimal in-memory session store for local development.
- Define `ChatSessionStore` protocol so relational persistence can be added without changing runtime behavior.
- Add API routes for web chat:
  - `POST /chat/messages`
  - `GET /chat/sessions/{session_id}`
  - `POST /chat/sessions/{session_id}/cancel`
- Add static bearer-token dependency for web chat endpoints.

### Out Of Scope

- Telegram webhook implementation.
- Full frontend UI.
- LLM router-agent behavior.
- Full answer generation.
- Rich correction application.

### Completion Criteria

- A normalized text message can call the runtime.
- The runtime can call the ingestion facade.
- The runtime can return a structured response with one default `primary_text`.
- Pending process context can be represented, attached to a later message, resumed when appropriate, cancelled, and expired.
- Chat sessions and ingestion sessions remain separate and linked by process IDs.

## Wave 2: Telegram And Web Chat Consumers

Status: implemented with web/Telegram consumer adapters in `src/my_digital_brain/chat/`, Telegram webhook API routes in `src/my_digital_brain/api/routes/telegram.py`, and coverage in `tests/test_chat_consumers.py`.

### Summary

Add concrete consumer adapters for Telegram and web chat.

### Telegram Changes

- Add Telegram settings.
- Use webhook delivery for deployed Telegram integration.
- Polling can remain a local development fallback if it is useful.
- Normalize Telegram text messages.
- Normalize Telegram voice messages.
- Store or reference Telegram voice artifacts.
- Actual Telegram Bot API file download can be wired when media storage and transcription are connected.
- Send text responses and clarification questions.
- Keep Telegram update payloads outside business logic.

### Web Chat Changes

- Add backend API endpoints usable by a frontend chat UI.
- Add frontend-ready response schema.
- Support text messages.
- Support audio upload when local media storage and speech-to-text are configured.
- Render `primary_text` as the main assistant message.
- Optionally render structured sidecars:
  - actions
  - evidence
  - pending process status
  - error or diagnostic details when appropriate

The web chat should be a perfect substitute for Telegram for core workflows:

- store a memory
- answer a clarification
- ask a memory question
- propose a correction

### Out Of Scope

- Sophisticated frontend graph dashboard.
- Full Graph-RAG answer generation.
- Agentic subprocess prompt design.

### Completion Criteria

- Telegram and web chat both use the same conversation runtime.
- A user can submit a text memory from both channels.
- A user can answer a clarification from both channels without the channel owning the clarification logic.
- Channel-specific formatting is isolated to adapters.

## Wave 3: Query, Answer, And Correction Facade Integration

Status: implemented with `MemoryBackendToolFacade`, deterministic and provider-backed answer generation hooks in `src/my_digital_brain/chat/tool_facade.py`, and coverage in `tests/test_chat_tool_facade.py`.

### Summary

Wire the tool facade to graph query/context services and create the baseline for grounded answers and correction proposals.

### Key Changes

- Implement `query_memory_context` using graph query/context services.
- Return low-noise context packages suitable for answer generation.
- Add simple answer-generation path through AI provider abstraction when configured.
- Add evidence/source summary in responses.
- Implement first correction proposal contract.
- Require confirmation for risky correction actions.
- Add response formatting for:
  - answer text
  - source/evidence notes
  - uncertainty notes
  - clarification prompts
  - correction confirmations

### Out Of Scope

- Full semantic vector retrieval unless already available and needed.
- Contradiction judge.
- Rich correction/merge automation.
- Profile/personality memory agent.
- Maintenance agent.

### Completion Criteria

- The user can ask a memory question from Telegram or web chat.
- The backend can retrieve graph context for the question.
- The response can include grounded evidence notes.
- The user can propose a correction and receive a safe next step.

## Later Work

- Dedicated agentic-process design plan.
- Router agent behavior and prompt protocol.
- Ingestion subprocess behavior and toolboxes.
- Query subprocess behavior and answer synthesis policy.
- Correction subprocess behavior.
- Contradiction judge behavior.
- Profile/personality memory agent.
- Rich vector-based Graph-RAG.
- Frontend graph visualization dashboard integration.
- Mobile client.

## Guardrails

- Chat adapters do not own memory business logic.
- Conversation runtime does not directly mutate graph storage.
- Tool facade operations call backend services and return structured results.
- LLM-facing tools must have concise, explicit schemas and descriptions.
- Mutating operations must be auditable.
- Pending processes must expire.
- Pending process context must enrich the next processing step; it must not force the next user message into a rigid route.
- Conversation history should be available for context building, but raw history should not be dumped into every model call.
- Tool loops must have limits when agentic behavior is introduced.
- Channel-specific payloads must not leak into ingestion or graph services.
- Web chat and Telegram should remain behaviorally equivalent for core workflows.
