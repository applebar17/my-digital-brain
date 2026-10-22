# Task 2.3.1 — implement the base state invocation boundary

**Status: Complete**

## User story

As a state author, I want one typed invocation method for direct calls and
agent-as-tool calls, so all states share the same history/client lifecycle.

## What and why

Build the base state that validates invocation, creates its local transcript,
appends the request once, calls `LLMInterfaceCore`, and maps the client outcome
to a typed state result. Include the minimal handoff for `awaiting_input`: yield
the continuation to the caller without a fabricated tool output, then resume
the same logical invocation after the answer arrives and return one result for
the original provider call. Do not implement provider calls, tool loops, or
product-specific prompt construction here.

## Where

- `src/product/agentic/state.py` and framework invocation/result contracts.
- Client integration and state tests under the `product` test namespace.

## Functional communication DTOs

Input: state purpose/context, the caller-selected history projection, request,
optional structured-output model, and toolbox. For a child invocation, its
parent selects that projection explicitly; the child does not choose or fetch
its starting history. Output: final assistant result, optional
validated artifact, or a typed `awaiting_input` continuation / unrecoverable
runtime outcome. A later answer resumes the same `StateHistory`. The client
owns batch execution: all mapped calls finish before the next provider request,
normal tool failures become per-call error outputs, and an external-input pause
retains the whole batch until all answers are available. It then sends all
matched outputs together in provider call order. Nested invocation uses the
same state input/output semantics.

## Dependencies and acceptance

- Depends on Issues 2.1 and 2.2.
- Each state start or resume delegates once to the client entrypoint; the
  client owns all provider turns and tool-loop iterations for that call.
- The client/state boundary can return control while a mapped tool awaits UI
  input, retain every call in that provider batch, then resume only when all
  pending inputs have outputs correlated to their original provider call IDs.
- A function or per-call output-preparation failure produces an error tool
  output; it cannot strand sibling calls or result in a partial provider batch.
- Multiple mapped calls can execute concurrently, but the next provider
  request contains exactly one output per call in the original call order.
- Direct and child-tool invocation use the same public state entrypoint.
- Test outputs cannot confuse tool payloads with assistant final messages.
