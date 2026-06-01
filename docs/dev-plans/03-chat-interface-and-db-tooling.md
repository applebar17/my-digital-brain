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
sessions, pending clarification state, response formatting
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
- Pending clarification state can be stored, resumed, cancelled, and expired.
- Telegram and web chat remain thin adapters with no memory business logic.
- The tool facade mirrors backend service capabilities without exposing raw graph CRUD or arbitrary database access.

## Locked Architecture Decisions

- Chat channels are adapters, not business logic owners.
- Telegram and web chat must call the same backend runtime.
- The conversation runtime owns channel-neutral message handling, session state, pending clarification routing, and response shaping.
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
- pending clarification reference
- conversation/session state
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
- `pending_session_id`
- `received_at`
- `metadata`

These contracts are transport contracts, not memory extraction contracts.

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
- Support pending clarification UI.
- Avoid memory business logic in frontend code.

Future mobile or desktop clients should reuse the same normalized contracts.

### Conversation Runtime

The conversation runtime coordinates channel-neutral message handling.

Responsibilities:

- Receive normalized messages from adapters.
- Store or reference source input before processing.
- Detect pending clarification sessions.
- Route clarification answers to the correct pending process.
- Call the backend tool facade.
- Return channel-neutral response objects.
- Keep session state minimal and expiring.
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
- `resume_pending_clarification`
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
- optional pending-session metadata

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
- Tool exposure to agents and subprocesses requires separate discussion.

## Wave 1: Channel-Neutral Chat Runtime

### Summary

Create the shared chat contracts, conversation runtime, session store interface, and tool facade skeleton.

### Key Changes

- Add chat package, for example `src/my_digital_brain/chat/`.
- Add contracts for:
  - `ChatChannel`
  - `IncomingChatMessage`
  - `IncomingMediaRef`
  - `ChatResponse`
  - `ChatResponsePart`
  - `ConversationSession`
  - `PendingProcessRef`
- Add conversation runtime service:
  - receive normalized messages
  - detect pending clarification state
  - call tool facade operations
  - return channel-neutral responses
- Add tool facade skeleton:
  - `start_memory_ingestion`
  - `query_memory_context`
  - `propose_memory_correction`
- Add minimal in-memory session store for local development.
- Add API routes for web chat:
  - `POST /chat/messages`
  - `GET /chat/sessions/{session_id}`
  - `POST /chat/sessions/{session_id}/cancel`

### Out Of Scope

- Telegram webhook implementation.
- Full frontend UI.
- LLM router-agent behavior.
- Full answer generation.
- Rich correction application.

### Completion Criteria

- A normalized text message can call the runtime.
- The runtime can call the ingestion facade.
- The runtime can return a structured response.
- Pending clarification state can be represented and resumed by id.

## Wave 2: Telegram And Web Chat Consumers

### Summary

Add concrete consumer adapters for Telegram and web chat.

### Telegram Changes

- Add Telegram settings.
- Add webhook or polling adapter decision.
- Normalize Telegram text messages.
- Normalize Telegram voice messages.
- Store/download voice artifacts.
- Send text responses and clarification questions.
- Keep Telegram update payloads outside business logic.

### Web Chat Changes

- Add backend API endpoints usable by a frontend chat UI.
- Add frontend-ready response schema.
- Support text messages.
- Support audio upload when local media storage and speech-to-text are configured.
- Return structured response parts:
  - assistant text
  - status
  - clarification request
  - evidence summary
  - error details

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
- A user can answer a clarification from both channels.
- Channel-specific formatting is isolated to adapters.

## Wave 3: Query, Answer, And Correction Facade Integration

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
- Tool loops must have limits when agentic behavior is introduced.
- Channel-specific payloads must not leak into ingestion or graph services.
- Web chat and Telegram should remain behaviorally equivalent for core workflows.
