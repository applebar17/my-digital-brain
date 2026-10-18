# Task 3.1.3 — preserve the human-interaction persistence boundary

**Status: Not started**

## User story

As the chat application, I want an awaiting-input interaction and its answer
associated with the paused state run, so the correct conversation can resume
after the user responds.

## What and why

Identify the existing API/storage mechanisms that persist and resolve a pending
interaction. Adapt the minimal boundary to the documented continuation DTO;
do not build a new clarification subsystem or place frontend persistence inside
the generic framework.

## Where

- Product API/chat interaction adapter and existing clarification persistence
  service migrated under `product`.
- Continuation storage integration is exercised in Wave 5 end-to-end tests.

## Functional communication DTOs

The application stores a channel-readable question/choice packet linked to the
paused state run and pending interaction. User response DTO returns the selected
or free-text answer to the waiting state/tool. The provider call ID is retained
as runtime correlation, not exposed to the user.

## Dependencies and acceptance

- Depends on Issue 2.2 continuation contract and the Wave 0 chat/clarification
  integration census.
- Existing user-visible question/answer semantics remain available.
- Only the minimum state linkage needed to resume is persisted.
- No dedicated clarification runtime or duplicate frontend flow is introduced.
