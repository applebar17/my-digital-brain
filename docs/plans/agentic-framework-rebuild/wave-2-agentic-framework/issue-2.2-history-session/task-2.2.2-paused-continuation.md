# Task 2.2.2 — support paused state continuation

**Status: Not started**

## User story

As an application state that requested human input, I want to resume the same
state-local conversation after the answer arrives, so the invoker can continue
without a fabricated assistant/tool message or a new unrelated session.

## What and why

Represent the paused transcript and open interaction using the existing
continuation contract. The history framework preserves the state linkage;
storage and API endpoints remain application responsibilities.

## Where

- `src/product/agentic/history/` continuation contract and lifecycle.
- Application persistence adapter is specified and implemented in Wave 5.

## Functional communication DTOs

The pause carries a state-run reference, interaction/question packet, and the
open provider call correlation needed by the client. The user answer is
validated by the application tool, then returned as the original call's one
tool result; provider call IDs remain protocol metadata.

## Dependencies and acceptance

- Depends on Task 2.2.1 and the client continuation behavior in Wave 1.
- A paused state retains exactly the minimum transcript and linkage needed to
  resume; a completed state releases local history.
- No separate clarification runtime or frontend-specific state is introduced.
