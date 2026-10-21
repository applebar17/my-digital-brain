# Task 2.3.1 — implement the base state invocation boundary

**Status: Not started**

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
runtime outcome. A later answer resumes the same `StateHistory`; the client
appends the single matched tool result and continues its existing loop. Nested
invocation uses the same state input/output semantics.

## Dependencies and acceptance

- Depends on Issues 2.1 and 2.2.
- Client is invoked exactly once per configured main session; client owns its
  internal provider/tool loop.
- The client/state boundary can return control while a mapped tool awaits UI
  input, then resume with one externally completed result correlated to the
  original provider call ID.
- Direct and child-tool invocation use the same public state entrypoint.
- Test outputs cannot confuse tool payloads with assistant final messages.
