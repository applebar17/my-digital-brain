# Task 1.2.2 — verify provider calls and tool continuation

**Status: In progress**

## User story

As an invoking state, I want every provider tool call—including mapped
function failures—to return one correlated result and resume the caller, so a
tool exception alone does not terminate the interaction.

## What and why

Test the accepted provider path, typed mapping, tool-call cap, and final
tool-free provider call. On a mapped-function exception, produce one
fabricated error tool result that explains the failure and offers useful hints;
do not send this behavior as prompt guidance.

## Where

- `product.ai.ai_clients` core and provider adapter tests.
- Direct runtime dependencies used by the selected client package in
  `pyproject.toml` and `uv.lock`.
- The typed mapping seam consumed later by `product.agentic`.

## Functional communication DTOs

`ProviderToolCallDTO` identifies the requested operation and validated input;
`ToolResultDTO` carries either the successful functional output or a
human-readable tool error. The client pairs that result to the provider call ID
and continues the same transcript. The ID is protocol metadata, not state
business data.

## Dependencies and acceptance

- Depends on Task 1.2.1.
- Each provider-issued call receives one matching output; mapped handlers are
  invoked at most once, including when they raise `TypeError`.
- Handler failures produce an informative error result and the provider is
  called again with the updated transcript.
- Calls beyond the configured call cap receive correlated synthetic error
  outputs; the next provider request has no toolbox and the client returns the
  provider's final assistant response.
- Scenario coverage combines success, handler exception, multiple calls,
  callable child-agent handling, cap recovery, and final assistant response.
- A tool result is never returned as the final assistant response.
- A provider call ID already handled in the session is skipped on later turns;
  it is neither executed again nor given another output.
- Successful and failed results use one `ToolOutputDTO` with `status="ok"` or
  `status="error"`; the error payload is included only for failures.
