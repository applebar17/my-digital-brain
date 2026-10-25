# Task 4.3.5 — compose the deterministic ingestion workflow

**Status: Not started**

## User story

As the application, I want a deterministic workflow to pass typed results
between ingestion states in the required order, so dependent writes use current
references and the root caller receives one useful outcome.

## What and why

Wire each accepted state into the deterministic workflow as its vertical slice
is completed. This final task checks the full accepted sequence, handoff data,
and dependencies end to end; it is not the first time the states are connected.
Implement `MemoryIngestionWorkflow(BaseWorkflow)` with explicit step
declarations, so the runtime execution order and the inspector graph use the
same composition. Expose an annotated `ingest_memory` method and register its
bound method as the chatbot tool handler. The workflow result returns to
`ConversationEntryState` as the matched tool output; that state generates the
user-facing reply.
Reasoning/planning may guide state behavior, but workflow handoffs determine
which outputs become inputs to subsequent steps. Do not introduce a generic
workflow DSL or an autonomous replacement for this sequence.

## Where

- `src/product/application/workflows/memory_ingestion.py`, inheriting the
  `BaseWorkflow` from Issue 4.P.
- `ingest_memory` tool registration in `src/product/application/tools/`.
- State invocation DTOs/results and typed graph/tool boundaries.

## Functional communication DTOs

The workflow carries source/owner context, reasoning/planning artifacts,
reference-context updates, node resolution/write results, memory/context
results, and relationship results. It returns a concise aggregate outcome with
successful writes, recoverable failures, clarification outcome if any, and
useful local refs; provider transcripts stay inside each state history.
The tool input is the typed workflow request; the tool's successful domain
output is the workflow result. The generic client still owns provider call-ID
pairing and wraps that result once.

## Dependencies and acceptance

- Depends on the state inventory and all state slices confirmed by Issue 4.0;
  the current Tasks 4.3.1–4.3.4 may be revised to match that inventory.
- Completes the `ingest_memory` binding in the conversation-entry toolbox
  created by Task 4.1.1.
- A context or relationship is not written before required target refs resolve.
- A tool failure is returned to the invoking state and the workflow does not
  silently fabricate success or apply a deterministic global break.
- The local inspector shows the workflow's actual step dependencies and each
  configured state's prompt, reasoning/planning stages, toolbox, and contracts.
- End-to-end tests assert data passed between each state, not only final DB
  counts.
