# Task 4.1.2e — compose memory query with conversation entry

**Status: Not started**

## User story

As the conversation-entry state, I want `query_memory` bound to the concrete
memory-query state so its compact result returns through the original tool call
and I can produce the final user-facing response.

## What and why

Replace the temporary `query_memory` capability contract and handler with the
reviewed `MemoryQueryState` request/result contract. Application composition
binds the retrieval service, owner scope, shared reference mapper, prompt
service, LLM client, history projection, and search toolbox.

This is an agent-as-tool composition, not a new deterministic workflow. The
child state owns its local transcript and returns one compact matched tool
output. `ConversationEntryState` resumes its existing provider loop and owns
the final chat response.

The temporary `ingest_memory` registration remains until the concrete
`MemoryIngestionWorkflow` is delivered in Task 4.3.5.

## Where and acceptance

- Update conversation-entry toolbox composition without adding a second tool
  loop or compatibility handler.
- Expose the configured child state and search toolbox through the existing
  local workflow/state inspection surface.
- Tests cover direct memory-query invocation, nested invocation, matched parent
  tool-call behavior, compact child output, and parent final-response ownership.
