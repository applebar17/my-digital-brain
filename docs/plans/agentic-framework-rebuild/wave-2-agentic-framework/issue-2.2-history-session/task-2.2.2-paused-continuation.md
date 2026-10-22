# Task 2.2.2 — support paused state continuation

**Status: In review**

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

The continuation carries the complete typed provider-call batch, including
call IDs, completed outputs, and outstanding interaction packets, alongside a
copied `StateHistory` snapshot. It does not duplicate state-history identity or
linkage in another DTO. A reasoning/planning pause additionally carries its
internal stage cursor and the canonical state transcript to resume after that
stage completes. Runtime handlers and toolbox objects are re-supplied by the
configured state, not serialized. After the answer is validated, the client
resumes the same batch and returns one result per original provider call ID;
no tool result or next provider call is emitted while a batch is incomplete.

## Dependencies and acceptance

- Depends on Task 2.2.1. State/client handoff and externally supplied tool
  result resumption are implemented in Task 2.3.1.
- A paused state retains exactly the minimum transcript and linkage needed to
  resume; a completed state releases local history.
- Pause and resume do not duplicate the invocation request or the original
  assistant tool-call turn.
- A serialized stage continuation restores both the correct stage cursor and
  canonical state transcript.
- No separate clarification runtime or frontend-specific state is introduced.
