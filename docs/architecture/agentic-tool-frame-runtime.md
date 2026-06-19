# Agentic Tool Frame Runtime

## Purpose

This document locks the target runtime model for agentic chat, memory ingestion,
querying, clarification, and graph updates.

The direction is deliberately simple:

```text
history down, compact result up
```

Each agentic process owns a provider message history while it is running. When a
process calls another agentic process, the child gets its own frame and local
history. When the child completes, its internal trace is compacted into one tool
result returned to the parent tool call.

## Locked Decisions

- Production chat runtime is agentic only.
- There is no separate deterministic conversation runtime path.
- State/process transitions happen through explicit tool calls, not
  `handoff_target` metadata.
- `pending_process` is not a production orchestration concept.
- `needs_user_input` is not used as internal flow control.
- Clarification is a provider tool-call continuation.
- Transport-level statuses may expose UI state such as
  `awaiting_clarification`, but they do not decide internal process routing.
- Graph writes stay deterministic behind tools.
- Failed or unsupported flows should fail visibly rather than silently falling
  back to legacy behavior.

## Conversation Entry

`conversation_entry` is the only top-level chat state.

It should expose a small toolbox:

- `query_memory`: answer a question by querying/hydrating the memory graph.
- `ingest_memory`: process a user memory, correction, update, transcript, or
  source text into graph changes.

The entry state should not expose every low-level graph write or planner tool.
Its job is to choose whether the user is asking to query memory or process new
information.

Example:

```text
user message
-> conversation_entry
-> model calls ingest_memory(source_text=...)
-> backend starts a child memory_ingestion frame
-> child completes
-> compact ingestion result returns to the conversation_entry tool call
-> conversation_entry continues and answers the user
```

## Agentic Frame Model

An `AgenticFrame` is the runtime unit of an LLM-owned process.

It stores:

- frame id;
- state id;
- parent frame id, if nested;
- parent tool call id, if nested;
- provider messages for this state;
- compact context payload;
- active tool call id/name when interrupted;
- active clarification packet, if any;
- status for observability and UI;
- compact trace/debug metadata.

Frames are not pending-process records. They are provider-message continuation
records.

## Nested Tool Execution

Nested agentic execution follows this contract:

```text
parent frame
-> assistant calls child-starting tool
-> backend creates child frame
-> child frame runs its own LLM/tool loop
-> child may call deterministic tools
-> child may ask clarification
-> child completes
-> backend appends one compact tool result to the parent tool_call_id
-> parent frame continues
```

The parent does not receive the child's full internal message trace. It receives
a compact result with the useful outcome, created/updated refs, diagnostics, and
failure/clarification state if relevant.

## Clarification

Clarification is not a pending-process workflow.

It is an interrupted tool call inside an agentic frame:

```text
frame messages
-> assistant calls request_user_clarification
-> backend stores the frame with the tool call open
-> UI renders the structured clarification packet as workflow state
-> user answers one or more questions
-> backend validates answers structurally
-> backend appends exactly one tool message for the original tool_call_id
-> same frame resumes with the same state-local message history
```

Clarification prompt and answer records may be retained in backend/session
history as hidden internal context, but they are not normal chat bubbles.

The UI may use statuses such as `awaiting_clarification` to render the
clarification widget. Those statuses are API visibility states only. The actual
continuation rule is the open tool call in the stored frame.

## Memory Ingestion

Memory ingestion should be a child agentic process started by
`conversation_entry` through `ingest_memory`.

The outer ingestion process may have a deterministic macro-shape:

```text
retrieve context
-> reason
-> plan
-> execute plan actions
-> summarize result
```

Inside those steps, the model can use tools where the task requires judgement,
context lookup, or clarification.

The planner should produce explicit structured plan actions. Backend code then
routes each action to the proper deterministic tool or child agentic state.

## Planner To Writer Contracts

The planner should not mutate the graph directly. It should produce a validated
artifact shaped like:

```text
MemoryPlan
  plan_id
  source_text
  context_refs
  actions: list[MemoryPlanAction]

MemoryPlanAction
  action_id
  action_type
  target_refs
  rationale
  payload
  dependencies
```

Initial action types:

- `create_memory_log`
- `create_node`
- `update_node`
- `create_relationship`
- `create_relationship_state`
- `ask_clarification`

Execution mapping:

```text
create_memory_log          -> deterministic write tool
create_node                -> deterministic write tool
update_node                -> graph_update child frame/tool
create_relationship        -> deterministic write tool
create_relationship_state  -> deterministic relationship-state service/tool
ask_clarification          -> request_user_clarification
```

This keeps planning semantic and graph writes deterministic.

## Graph Update

`graph_update` remains an agentic state because updates can require multiple
read/write attempts, target resolution, clarification, and recovery from
structured tool errors.

It can be invoked in two ways:

- as a child process from memory ingestion when the planner infers an update is
  needed;
- optionally as a direct child process if a future entry tool intentionally
  exposes direct graph maintenance.

For now, the preferred top-level path is:

```text
conversation_entry -> ingest_memory -> planner action update_node -> graph_update
```

This avoids making `conversation_entry` choose between competing write/update
tools.

## Determinism Boundary

Allowed deterministic behavior:

- schema validation;
- graph consistency validation;
- ID creation and alias resolution;
- source/evidence attachment;
- graph writes;
- vector refresh after mutation;
- tool argument validation;
- child frame creation and provider message continuation.

Deprecated deterministic behavior:

- routing from one agentic state to another through `handoff_target`;
- pending-process review as the normal continuation path;
- model-visible `resume_pending_process`, `pause_pending_process`, or
  `cancel_pending_process` tools;
- hidden fallback from a failed agentic process to old deterministic chat
  behavior;
- treating `needs_user_input` as an internal state transition mechanism.

## Cleanup Target

The implementation should remove or quarantine legacy code instead of wrapping
it indefinitely.

Production runtime should not depend on:

- deterministic chat mode;
- pending-process context for agentic continuation;
- pending-process review state;
- handoff metadata interpretation;
- correction-intake legacy routing;
- facade-level `start_memory_ingestion` clarification/resume behavior.

If a legacy persistence table must remain for migration compatibility, it should
not be part of active runtime routing.
