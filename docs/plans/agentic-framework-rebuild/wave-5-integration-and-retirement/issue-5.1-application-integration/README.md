# Issue 5.1 — compose API/chat runtime and verify end-to-end flows

**Status: Not started**

Connect the deterministic application workflow/orchestrator, history session,
and root state to the existing API/chat boundaries. Verify normal completion,
nested tool use, recoverable tool failure, and clarification continuation as
behavioral cases of the same interaction contract.

## Tasks

- [Task 5.1.1 — compose application runtime at the API boundary](task-5.1.1-compose-api-runtime.md)
- [Task 5.1.2 — verify end-to-end chat and ingestion behavior](task-5.1.2-end-to-end-verification.md)

## Functional communication DTOs

API request supplies user message, conversation/owner context, and channel data.
Application runtime creates/loads history and invokes the root state. API
response is either the assistant final message or a typed interaction packet
that the existing frontend can render; a tool result is never the final chat
response. Ingestion result returns to its invoker before the root agent answers.

## Dependencies

- Completed workflow/state slices and any interaction persistence boundary
  those states actually require.
- Existing API/chat response contract from the Wave 0 integration census.
