# Task 4.3.0a — implement invocation context and inherited child history

**Status: Complete**

## User story

As an agentic state invoking another state or workflow through a tool, I want
the invoked capability to inherit the relevant caller history automatically,
so model-visible source context does not have to be regenerated or passed as
tool arguments.

## What and why

Implement one framework-owned, backend-only invocation context for every
registered tool call. It identifies the active parent state run and original
provider call and gives agent/workflow handlers access to the same
`AgenticHistorySession`. It is execution metadata and must never enter the
provider-facing input DTO.

Add one centralized history operation that projects a child history from the
parent state. The default projection preserves selected conversational turns
and the current user message while excluding the parent's system prompt, open
tool-call turn, tool outputs, traces, and provider metadata. A child supplies
its own system prompt and purpose request.

The same mechanism applies when the registered handler invokes an agentic
state or a deterministic workflow whose first step invokes a state. Do not add
an ingestion-specific history DTO, a second transcript manager, or a model
argument carrying copied conversation content.

## Where

- `src/product/agentic/contracts/` backend invocation context contract.
- `src/product/agentic/history/` inherited child projection.
- `src/product/agentic/state.py` active parent-state scope.
- `src/product/agentic/tools/` registered-handler access to invocation context.
- `src/product/ai/ai_clients/` provider call-ID propagation only where the
  generic client owns that ID.

## Functional communication boundary

The model sends only the registered tool input DTO. Independently, the
framework supplies the handler with the active history session,
`parent_state_run_id`, and provider-issued parent call ID. A child invocation
uses the centralized projection and linkage; it does not restart from global
master history or receive the raw parent provider transcript.

## Previous and current behavior

The deprecated runtime's `run_child_frame` copied `ConversationContext`,
`current_text`, shared reference context, and parent frame/tool-call identity
into a child-specific execution context. `AgenticHistoryService` then rendered
role-preserved history and the current message for the child. This demonstrates
the functional behavior to preserve.

That implementation is not the migration target. It combined a large
application execution context, persisted agentic frames, metadata dictionaries,
and several competing history paths such as master-history projection,
state-specific message rendering, and ingestion source reconstruction.

The current `product` runtime has the opposite gap: `MemoryQueryState` and
`ClarificationState` initialize themselves from global `master_history`, while
registered handlers receive no parent state/tool invocation context.
Clarification therefore attaches parent linkage only after a pause, and memory
query has no equivalent inherited child linkage.

Task 4.3.0a keeps the old behavior's useful outcome—caller history, current
message, shared session, and exact parent-call correlation—but implements it
once in the small target framework. Task 4.3.0b removes the target workarounds
after that mechanism exists.

## Dependencies and acceptance

- Depends on the Wave 2 state, history, and tool-loop contracts.
- Works for both agent-backed and workflow-backed registered tools.
- Current user content reaches the child through inherited history, not tool
  arguments.
- Parent/child linkage exists when the child starts rather than being repaired
  only after a pause.
- Parallel tool handlers receive the correct immutable call context.
- Functional tests cover parent state → child state and parent state → workflow
  → first child state inheritance.

