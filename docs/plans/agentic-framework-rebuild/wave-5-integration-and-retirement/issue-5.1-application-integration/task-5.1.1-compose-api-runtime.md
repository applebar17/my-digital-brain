# Task 5.1.1 — compose application runtime at the API boundary

**Status: Not started**

## User story

As a chat/API caller, I want one application composition boundary to initialize
history, owner context, workflow dependencies, and the root state, so the API
does not know provider/tool-loop internals.

## What and why

Wire application services and states in one deterministic composition point.
Preserve existing endpoint behavior and request/response DTOs unless the new
state result requires a specifically agreed adjustment.

## Where

- `src/product/application/workflows/` composition root.
- `src/product/api/` route/service adapter and durable history/interactions.
- Frontend contract only where the existing response cannot represent an
  accepted state outcome.

## Functional communication DTOs

The API-to-runtime request carries message, conversation identity, owner
projection/source, and channel context. The runtime-to-API result carries final
assistant content or an awaiting-input packet with interaction reference and
renderable question. Provider transcript and tool error payloads remain
internal; final response content is created by the root assistant state.

## Dependencies and acceptance

- Depends on the selected Wave 4 root state and workflow composition.
- API does not start or manage provider calls itself.
- Existing chat persistence stores accepted user/assistant messages and the
  minimum paused continuation needed for resume.
- No new generic frontend state machine is added without a concrete contract
  gap.
