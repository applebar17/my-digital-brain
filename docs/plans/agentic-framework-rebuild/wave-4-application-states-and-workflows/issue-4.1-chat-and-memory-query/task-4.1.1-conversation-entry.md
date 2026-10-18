# Task 4.1.1 — implement conversation-entry state

**Status: Not started**

## User story

As a chat user, I want my request answered by the conversation-entry agent,
which can use explicitly configured application states as tools, so child
results are interpreted into one appropriate final response.

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
context. A child tool receives its own typed purpose/context; its result returns
to the entry state as functional data. Output: final assistant text or the
framework's existing awaiting-input continuation, never raw tool JSON.

## Dependencies and acceptance

- Depends on Wave 2 base state/history and Wave 3 tool registrations.
- Root invocation uses the shared session and its own local transcript.
- Child-agent output is returned to the invoking state, not rendered directly
  as the chat answer.
- Prompts use the documented versioned prompt lifecycle.
