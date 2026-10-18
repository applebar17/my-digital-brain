# Task 1.2.2 — verify provider calls and tool continuation

**Status: Not started**

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
- The typed mapping seam consumed later by `product.agentic`.

## Functional communication DTOs

`ProviderToolCallDTO` identifies the requested operation and validated input;
`ToolResultDTO` carries either the successful functional output or a
human-readable tool error. The client pairs that result to the provider call ID
and continues the same transcript. The ID is protocol metadata, not state
business data.

## Dependencies and acceptance

- Depends on Task 1.2.1.
- Tests cover success, handler exception, multiple calls, call-cap recovery,
  nested agent handler, and final assistant response.
- A tool result is never returned as the final assistant response.
- No duplicate output is attached to one provider call ID.
