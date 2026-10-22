# Task 2.1.2 — compose and invoke typed toolboxes

**Status: Done**

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

- Framework tool declaration DTO in
  `src/product/ai/ai_clients/protocols/protocol_tools.py`.
- Agent-specific toolbox composition and typed handler binding under
  `src/product/agentic/tools/`.
- Client tool-spec compilation in `src/product/ai/ai_clients/`.

## Functional communication DTOs

The state supplies one `ToolBox`; its model-visible definitions and callable
mapping are derived from the same registrations. A parent tool input is
validated as the registered input DTO and translated by its bound handler to a
child invocation. The child's completed result is mapped to the handler's
typed success DTO, then the client wraps it in the one provider-matched tool
output. If the child pauses for human input, the session pauses and resumes;
no pending tool-result status is added.

## Dependencies and acceptance

- Depends on Task 2.1.1.
- Model-visible tools and mapped functions are derived from the same typed
  registrations.
- Raw provider arguments are validated once as the registered input DTO and
  passed to the typed handler; success or failure becomes one correlated
  client `ToolOutputDTO`, then the invoking model call resumes.
- Tests cover a deterministic function, an agentic child state, and an
  unavailable/misconfigured mapping returned as an explanatory tool error.
- `tests/test_ai_client_tool_continuation.py` verifies a parent
  `BaseAgenticState` invokes a mapped child state, then receives its typed result
  under the original provider call ID before producing its assistant response.
