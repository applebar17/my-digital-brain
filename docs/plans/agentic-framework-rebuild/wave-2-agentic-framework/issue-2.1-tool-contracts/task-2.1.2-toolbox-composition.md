# Task 2.1.2 — compose and invoke typed toolboxes

**Status: Not started**

## User story

As an agentic state, I want an explicit toolbox of partially bound deterministic
functions and child states, so the same callable map supplies the model schema
and executable implementation.

## What and why

Compose named tool definitions and mapped handlers without global discovery,
string-only handler dispatch, or mutable shared registries. Allow a state
invoked as a tool to use the same registered-tool contract as a normal
function.

## Where

- Generic toolbox composition under `src/product/agentic/tools/`.
- State invocation boundary in `src/product/agentic/`.

## Functional communication DTOs

The state supplies a `ToolBox` containing each tool's definition and bound
executable. A parent tool input is translated to a child `StateInvocation`;
the child's completed result is mapped to the handler's typed success DTO, then
the client wraps it in the one provider-matched tool output. If the child
pauses for human input, the session pauses and resumes; no pending tool-result
status is added.

## Dependencies and acceptance

- Depends on Task 2.1.1.
- Model-visible tools and mapped functions are derived from the same typed
  registrations.
- Tests cover a deterministic function, an agentic child state, and an
  unavailable/misconfigured mapping returned as an explanatory tool error.
