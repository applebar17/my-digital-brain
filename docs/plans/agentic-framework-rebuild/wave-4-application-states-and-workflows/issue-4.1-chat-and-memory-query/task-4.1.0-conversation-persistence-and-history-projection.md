# Task 4.1.0 — prepare durable conversation and history projections

**Status: Not started**

## User story

As an application user, I want my conversations and user interactions stored
durably and loaded consistently, so the frontend can render my chat history
while `ConversationEntryState` receives the relevant conversational context.

## What and why

Prepare the application boundary between durable conversation storage and the
runtime `AgenticHistorySession` before implementing the chat-facing state. The
persisted conversation is the source for both frontend history and the selected
model context, but those projections are not identical.

Keep three responsibilities separate:

1. durable conversation entries survive requests and belong to one application
   user and conversation;
2. deterministic projections select what the frontend and the root model may
   see;
3. state-local provider transcripts retain tool calls and outputs only for the
   active invocation or a persisted pause/resume continuation.

Do not make `ConversationEntryState` fetch database records, authorize users,
or persist messages. A conversation application service performs those steps,
creates `AgenticHistorySession` from the selected model projection, and invokes
the state.

## Durable entry and projection semantics

The target conversation timeline must represent, with explicit typed variants:

- ordinary user and assistant messages;
- user-facing question/answer interactions, including their stable interaction
  reference and completion state;
- an explicitly promoted compact model-context entry only when later root
  turns need information that should not appear in the frontend.

One stored entry can be projected differently without duplicating its content:

| Entry | Frontend projection | Conversation-entry model projection |
| --- | --- | --- |
| User or assistant message | Normal chat item | Corresponding `user` or `assistant` message |
| Completed question/answer interaction | One readable interaction component | Ordered assistant question and user answer messages |
| Pending question | Readable pending interaction | Remains owned by its paused continuation; it does not start a new root turn |
| Explicit compact model-only entry | Excluded | Included only when deliberately promoted and selected |
| Raw tool call, tool output, trace, or reasoning artifact | Excluded | Excluded from future root turns; retained only by the active/paused state transcript or diagnostics |

Question and answer entries form one history-selection unit: a bounded model
projection must not keep an answer while dropping its question. Their frontend
representation may differ from ordinary message bubbles, but a session replay
must preserve the interaction in its original position.

## Runtime sequence

```text
authenticated application user + conversation id + new message
  -> validate conversation ownership
  -> append the user entry idempotently
  -> load bounded prior durable entries, excluding the new current message
  -> build the frontend projection and model-history projection
  -> AgenticHistorySession(model-history projection)
  -> ConversationEntryState(current message)
  -> append the completed assistant entry
  -> return the typed turn result
```

The frontend sends the conversation identifier, a client-generated message
identifier, and the new content. It does not send an authoritative copy of the
conversation history. Optional reply/selection identifiers are resolved
against backend-owned records rather than trusted as message content.

## Functional contracts

Define the smallest explicit DTOs needed for these boundaries:

- a submitted-message DTO with conversation ID, idempotency key, and content;
- durable conversation-entry variants for a normal message, a question/answer
  interaction, and an explicitly promoted compact model-only entry;
- a frontend-history result containing ordered renderable items and pagination
  information;
- a model-history projection containing ordered canonical `Msg` objects;
- a turn result containing the persisted user entry, completed assistant entry
  or awaiting-input interaction, and the canonical state outcome.

DTO fields must be justified by an active consumer. Do not add arbitrary
metadata bags, provider identifiers, graph identifiers, raw state transcripts,
or duplicated message text. The exact database mapping may reuse current chat
tables where their fields remain valid, but the DTOs above are the application
contracts.

## History selection baseline

Start with deterministic recent-history selection bounded by message count or
the client input budget. Preserve ordering and question/answer units. Append the
current request exactly once through `BaseAgenticState`; it must not also be in
the selected prior-history projection.

A stored rolling summary and semantic history retrieval are later
optimizations. Do not introduce either until a concrete context-window need is
measured. The projection boundary must allow that policy to change without
changing conversation persistence or `ConversationEntryState`.

## Ownership and concurrency boundary

The target service receives the authenticated application user identity from
the API/authentication boundary and scopes every conversation lookup to it.
Frontend-supplied owner identifiers are not trusted as authorization. Full
application-user/authentication integration remains after the AI migration,
but repositories and service methods must accept an owner scope so it is not
designed out.

Use the client message identifier for idempotent retries. The MVP permits one
active agentic turn per conversation; a new root turn must not race a paused or
running turn. The implementation may enforce this through the existing durable
conversation/process boundary without adding a second agentic status model.

## Where and affected logic

Target code introduced or completed by this task:

- `src/product/application/conversations/contracts.py` for durable entry,
  projection, submission, and turn DTOs;
- `src/product/application/conversations/repository.py` for the typed storage
  protocol and owner-scoped operations;
- `src/product/application/conversations/history.py` for deterministic frontend
  and model projections;
- `src/product/application/conversations/service.py` for the entrypoint sequence
  and `AgenticHistorySession` initialization;
- focused application tests for persistence/projection behavior and invocation
  context assembly.

Existing integration points to adapt only after the target boundary is ready:

- `src/my_digital_brain/api/routes/chat.py` for HTTP request/authentication
  adaptation;
- `src/my_digital_brain/chat/relational_store.py` and
  `src/my_digital_brain/storage/relational_models.py` for PostgreSQL mapping;
- `src/my_digital_brain/chat/runtime.py` and
  `src/my_digital_brain/agentic/history.py`, whose mixed legacy runtime/history
  responsibilities are not migrated into the new application service.

## Dependencies and acceptance

- Uses `AgenticHistorySession` as the only target runtime history owner.
- Persists ordinary messages and question/answer interactions once and derives
  both projections deterministically.
- The frontend history contains readable question/answer interactions but no
  provider/tool transcript.
- `ConversationEntryState` receives relevant completed question/answer context
  and any explicitly promoted compact model-only context.
- The current user request is appended once, not duplicated between durable
  history and the state invocation.
- Conversation ownership is represented in repository/service contracts even
  though the final authentication provider is deferred.
- Idempotent submission does not create duplicate user entries.
- No prompt, graph, memory-query, or ingestion behavior is implemented here.

## Out of scope

- final application-user and authentication-provider integration;
- long-term retention, deletion, export, and compliance policy;
- rolling LLM summaries or semantic selection of old chat messages;
- streaming transport and final frontend component styling;
- migration or deletion of legacy chat code before its callers move.
