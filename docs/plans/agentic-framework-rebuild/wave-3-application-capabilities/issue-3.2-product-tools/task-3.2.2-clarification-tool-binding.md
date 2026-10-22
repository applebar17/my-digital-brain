# Task 3.2.2 — define clarification interaction tool binding

**Status: Not started**

## User story

As a clarification-capable state, I want a typed tool to ask the user a
context-grounded question, so the existing frontend interaction can pause and
resume the same state conversation.

## What and why

Bind the state/tool's question request to the existing application interaction
service and its continuation contract. The question renderer is not a new
generic agentic framework component.

## Where

- `src/product/application/tools/` clarification-tool DTO and mapping.
- Existing clarification UI/API adapter, migrated/adapted under `product`.

## Functional communication DTOs

Question input contains a human-readable question, purpose/context, and any
answer options required by the channel. The pending interaction packet returns
to the application; after the user answers, the same tool receives the answer
and returns it as a typed tool result to the waiting child state.

The question uses the shared [user-interaction tool contract](../../../../ai-engineering/application-states/user-interaction-tools.md):
the backend owns its deadline and resolves either the user's answer or one
timeout result to the waiting tool call.

## Dependencies and acceptance

- Depends on Task 2.2.2 and Task 3.1.3.
- One question invocation maps to one user-visible interaction and one eventual
  matched result.
- Presentation-specific payload remains owned by the API/frontend contract.
