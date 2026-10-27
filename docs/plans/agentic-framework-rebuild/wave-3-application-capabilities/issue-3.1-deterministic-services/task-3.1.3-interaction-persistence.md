# Task 3.1.3 — preserve the human-interaction persistence boundary

**Status: In-process boundary implemented by Task 4.2.2; durable adapter deferred to Wave 5**

## User story

As the chat application, I want an awaiting-input interaction and its answer
associated with the paused state run, so the correct conversation can resume
after the user responds.

## What and why

If a reviewed state requires a user-input interaction, identify the existing
API/storage mechanisms and define the needed persistence boundary in that state
slice. Adapt only what is required; do not build a new clarification subsystem
or place frontend persistence inside the generic framework.

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

Task 4.2.2 implements the typed in-process continuation boundary and nested
child-to-parent resumption. Task 5.1.1 remains the owner of PostgreSQL/API
persistence and application composition; Wave 4 does not import the old
agentic-frame runtime.

See the [user-interaction tool contract](../../../../ai-engineering/application-states/user-interaction-tools.md)
for the single source of truth on deadline ownership and timeout semantics.
