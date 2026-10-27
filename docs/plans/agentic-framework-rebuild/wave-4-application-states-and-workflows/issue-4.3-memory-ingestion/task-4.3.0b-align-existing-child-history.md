# Task 4.3.0b — align existing child states with inherited history

**Status: Ready for review**

## User story

As a framework maintainer, I want every implemented child capability to use the
same inherited-history mechanism, so the new runtime has one active history
design and no state silently restarts from unrelated master history.

## What and why

Migrate existing target-runtime child handlers after Task 4.3.0a. Remove direct
child initialization from `AgenticHistorySession.master_history`, manual
post-pause parent-history linkage, and any duplicate projection helper made
obsolete by the framework mechanism.

The root `ConversationEntryState` may still begin from the durable conversation
projection supplied by the application. `MemoryQueryState`,
`ClarificationState`, and future workflow states inherit the projection selected
by their invoker and add only their purpose-specific request and typed context.

## Where

- `src/product/application/states/memory_query/`.
- `src/product/application/states/clarification/`.
- `src/product/application/tools/conversation_entry/` and clarification
  handoff handlers.
- Focused state, history, query, and clarification tests.

## Functional communication boundary

Inherited conversation history is framework context. State-to-state semantic
data remains in explicit DTO results and inputs; no child receives another
child's raw local transcript. Provider call IDs remain protocol correlation and
never become model-visible history content.

## Dependencies and acceptance

- Depends on Task 4.3.0a.
- Removes, rather than preserves, superseded target-runtime history paths.
- Memory query and clarification retain their existing functional outputs and
  tool behavior after migration.
- Root, child-agent, paused-child, and resumed-parent tests all use the same
  inherited-history implementation.
- No compatibility branch or deprecated history mode remains under `product`.

