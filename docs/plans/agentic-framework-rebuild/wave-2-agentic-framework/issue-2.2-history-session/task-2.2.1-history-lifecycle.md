# Task 2.2.1 — implement shared and state-local history

**Status: Not started**

## User story

As an orchestrator invoking multiple states, I want one shared history session
to provide each state its selected context and isolated local transcript, so
child conversations do not corrupt the parent provider transcript.

## What and why

Implement the documented history lifecycle, parent/child run linkage, explicit
master promotion, and completed-state cleanup. Keep provider message ordering
and tool-call IDs with `ai_clients`; history does not run tools or invent what
should be promoted.

## Where

- `src/product/agentic/history/` and typed contracts under
  `src/product/agentic/contracts/`.
- Focused unit tests for root, child, selected projection, promotion, and
  cleanup.

## Functional communication DTOs

`StateHistory` relates a state run to its parent and chosen master-history
projection. The state request and child result are not copied wholesale into
master history; promotion is an explicit caller-selected message/result.

## Dependencies and acceptance

- Depends on Wave 1 client support for canonical transcript handling.
- Root and child histories are distinct and correctly linked.
- The caller's history is not mutated when a state runs.
- No automatic summary, promotion policy, durable store, or provider loop is
  added beyond the specification.
