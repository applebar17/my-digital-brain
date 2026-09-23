# Conversation entry state

## Purpose

`ConversationEntryState` is the only top-level LLM state for a normal chat
message. It gives the model a deliberately small choice: respond directly,
query existing memory, or ingest new/corrected memory information.

It does not expose graph CRUD, extraction internals, clarification tooling, or
a separate correction route. A correction is handled through `ingest_memory`,
whose child state decides the appropriate work from its context.

## Invocation and context

The deterministic orchestrator creates the shared `AgenticHistorySession`,
selects the chat-wide history projection, and invokes this state with the
normalized current user message. The state uses a versioned conversation-entry
system prompt and the context-package contract for its prompt sections.

The minimal request contract is conceptually:

```python
class ConversationEntryRequestDTO(BaseModel):
    """The normalized current user request for top-level conversation routing."""

    model_config = ConfigDict(extra="forbid")

    user_message: str = Field(
        description="The current normalized user message to answer or route."
    )
```

History, provider route, prompt reference, and toolbox are invocation/runtime
configuration rather than copied request fields.

## Toolbox and behavior

The state is dynamic and receives exactly these model-visible capabilities:

- `query_memory`: an agentic tool that starts `MemoryQueryState`;
- `ingest_memory`: an agentic tool that starts `MemoryIngestionState`.

For greetings, ordinary discussion, and other non-memory requests, the state
answers directly. For a memory-dependent question it calls `query_memory`. For
new information, correction, update, transcript, or other memory source-like
content it calls `ingest_memory`.

It does not make an out-of-band routing decision after a tool returns. The
canonical provider loop appends the matched tool output and the same state
decides its next assistant response or further tool call.

## Completion

A direct answer is a normal completed assistant message. A child-state result
is visible only as the matched output to the original `query_memory` or
`ingest_memory` provider call; it cannot become a serialized final chat
message. The resumed conversation-entry session owns any final user-facing
reply.

Clarification initiated deeper in a child state follows that child's paused
continuation. Conversation entry does not create a duplicate clarification
packet or a second user-facing question.

## Verification

Tests cover direct-answer behavior, the two-tool surface, correct child-state
binding, matched child result handling, and the absence of graph-write,
clarification, correction-routing, or legacy handoff tools.
