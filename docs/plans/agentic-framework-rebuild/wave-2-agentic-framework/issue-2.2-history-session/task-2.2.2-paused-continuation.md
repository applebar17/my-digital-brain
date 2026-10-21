# Task 2.2.2 — support paused state continuation

**Status: In progress**

## User story

As an application state that requested human input, I want its state history
and open tool interaction represented as a continuation, so the same logical
tool invocation can complete after the answer arrives.

## What and why

Add the minimum typed continuation contract and history-session operations to
retain and retrieve a paused `StateHistory`. The Python request does not remain
blocked while the user answers: the state yields an `awaiting_input`
continuation to its caller, and a later request resumes that logical invocation.
The history layer does not call providers, build UI responses, or persist data.

## Where

- `src/product/agentic/contracts/` typed continuation DTO using the existing
  client `Msg` transcript type and a typed interaction packet.
- `src/product/agentic/history/` pause and resume lifecycle for the retained
  state run.
- Application persistence adapter is specified and implemented in Wave 5.

## Functional communication DTOs

The continuation carries a copied `StateHistory` snapshot (therefore its run
ID, parent linkage, and `Msg` transcript), a typed interaction/question packet,
and the open provider call ID. It does not duplicate state-history fields in a
second DTO. After the answer is validated, the state/client boundary resumes
the same transcript and returns one result for the original provider call ID;
no tool result is emitted while waiting.

## Dependencies and acceptance

- Depends on Task 2.2.1. State/client handoff and externally supplied tool
  result resumption are implemented in Task 2.3.1.
- A paused state retains exactly the minimum transcript and linkage needed to
  resume; a completed state releases local history.
- Pause and resume do not duplicate the invocation request or the original
  assistant tool-call turn.
- No separate clarification runtime or frontend-specific state is introduced.
