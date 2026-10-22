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

For tools that directly request user input, the backend interaction boundary
also owns a per-interaction response deadline. An answer before the deadline or
the timeout must resolve the same pending interaction into exactly one result
for the waiting tool call. The timeout is specific to UI-waiting tools; ordinary
mapped tools gain no pause or timeout behavior.

## Where

- Product API/chat interaction adapter and existing clarification persistence
  service migrated under `product`.
- Continuation storage integration is exercised in Wave 5 end-to-end tests.

## Functional communication DTOs

The application stores a channel-readable question/choice packet and the
minimum continuation needed to resolve the waiting state/tool call, including
its backend-enforced deadline. A user response DTO returns the selected or
free-text answer; expiration returns a deterministic timeout result. The
provider call ID is retained as runtime correlation, not exposed to the user.

## Dependencies and acceptance

- Depends on Issue 2.2 continuation contract and the Wave 0 chat/clarification
  integration census.
- Existing user-visible question/answer semantics remain available.
- Only the minimum state linkage needed to resume is persisted.
- The backend decides answer-versus-timeout resolution; the frontend timer is
  presentation only, and only one result is accepted for the interaction.
- No dedicated clarification runtime or duplicate frontend flow is introduced.

See the [user-interaction tool contract](../../../../ai-engineering/application-states/user-interaction-tools.md)
for the single source of truth on deadline ownership and timeout semantics.
