# Task 4.1.1 — implement conversation-entry state

**Status: Not started**

## User story

As a chat user, I want my request answered by the conversation-entry agent,
which can use explicitly configured child states or workflows as tools, so
their results are interpreted into one appropriate final response.

## What and why

Implement the root state using the generic framework, selected prompt version,
owner/context projection, and approved toolbox. It owns no provider loop or
domain service implementation.

## Where

- `src/product/application/states/conversation_entry.py` and its functional
  prompt/toolbox configuration.
- `product.application.workflows` composition boundary and current chat API
  adapter during transition.

## Functional communication DTOs

Input: user request, owner context, chosen conversation history, and channel
context. `query_memory` invokes a child state; `ingest_memory` invokes the bound
`MemoryIngestionWorkflow.ingest_memory` method. Each receives its typed request
and returns functional data as its matched tool output. Output: final assistant
text or the framework's existing awaiting-input continuation, never raw tool
JSON.

## Dependencies and acceptance

- Depends on Wave 2 base state/history. Define child tools and registrations
  from this state's reviewed behavior rather than assuming the current draft
  toolbox.
- Bind `query_memory` when its child state exists. Bind `ingest_memory` to the
  concrete workflow method in Task 4.3.5; do not add a placeholder handler.
- Root invocation uses the shared session and its own local transcript.
- Child-state and workflow results return to the invoking state as matched tool
  outputs; neither is rendered directly as the chat answer.
- Prompts use the documented versioned prompt lifecycle.
