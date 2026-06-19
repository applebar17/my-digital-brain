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
- `ingest_memory`: process the current user message/history as a memory,
  correction, update, transcript, or source-like input into graph changes.

The entry state should not expose every low-level graph write or planner tool.
Its job is to choose whether the user is asking to query memory or process new
information.

Example:

```text
user message
-> conversation_entry
-> model calls ingest_memory()
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

If a child interrupts for clarification, the child frame is stored as
`interrupted` and remains the UI-active frame. The parent frame is stored as
`waiting_child`, preserving the parent assistant tool call without becoming a
second user-facing clarification. When the child completes, the backend appends
one compact tool result to the parent tool call and resumes the parent.

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

## Query Memory

`query_memory` is a read-only child agentic process. It should not expose
`request_user_clarification`.

The query frame should retrieve what it can, hydrate graph context, and answer
from available memory. If retrieval is empty or ambiguous, it should return a
bounded answer that says there is not enough memory context instead of starting
a clarification workflow.

Typical query shape:

```text
conversation_entry
-> model calls query_memory(question=...)
-> backend starts memory_query child frame
-> semantic scoped retrieval
-> hydrate top hits into graph context packages
-> answer from hydrated context
-> compact query result returns to the conversation_entry tool call
```

## Memory Ingestion

Memory ingestion should be a child agentic process started by
`conversation_entry` through `ingest_memory`.

The first ingestion context step is semantic retrieval from the user message or
source-like history context:

```text
embed/query relevant source/history text
-> top-k scoped vector retrieval
-> hydrate top hits into graph context packages
-> pass hydrated context into reasoning and planning
```

The outer ingestion process may have a deterministic macro-shape:

```text
semantic retrieval + hydration
-> reason
-> plan
-> execute plan actions through child frames/tools
-> summarize result
```

Inside those steps, the model can use tools where the task requires judgement,
context lookup, or clarification.

The planner should produce explicit structured plan actions. Each action is then
handled by model-visible tools or child frames. Backend code validates tool
arguments and reports structured results, but the LLM decides the next action
after validation errors or blocked tool outputs.

## Planner To Writer Contracts

The planner should not mutate the graph directly. It should produce a validated
artifact shaped like:

```text
MemoryPlan
  plan_id
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
create_memory_log          -> memory_creation child frame
create_node                -> memory_creation child frame
create_relationship        -> memory_creation child frame
create_relationship_state  -> memory_creation child frame
update_node                -> graph_update child frame/tool
ask_clarification          -> request_user_clarification
```

The planner passes history/context plus one plan action to the child frame. It
should not duplicate the original source text as a separate field when that
source text is already present in the provider message history passed down to
the child.

This keeps planning semantic and graph writes deterministic.

## Memory Creation

`memory_creation` is a child agentic frame responsible for executing one
creation-oriented plan action.

Input shape:

```text
history/context messages
+ one MemoryPlanAction
+ hydrated graph context relevant to that action
```

It does not receive a duplicated `source_text` field when the source is already
available in history.

Available tools may include:

- `create_memory_log`;
- `create_graph_node`;
- `create_graph_relationship`;
- `create_relationship_state`;
- helper read tools for local context checks;
- `update_memory_graph` when the creation action discovers a related update is
  needed;
- `request_user_clarification` when the action cannot be completed safely from
  available context.

Tool implementations validate and write deterministically. If validation fails,
the tool returns a clear structured error result to the frame. The LLM decides
whether to retry, ask clarification, call another tool, or return failure.

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
- structured validation error reporting from tools;
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

## Implementation Waves

The migration should land as three build waves plus one stabilization wave. The
first three waves perform the actual architecture change; the fourth wave proves
that the old hidden behavior is gone.

### Wave 1: Contracts And Tool Interfaces

Goal: define the new runtime and process contracts before replacing behavior.

Scope:

- define or refine the `AgenticFrame` continuation contract;
- define `MemoryPlan` and `MemoryPlanAction`;
- define `memory_ingestion` context/result contracts;
- define `memory_creation` context/result contracts;
- define the shared structured tool-result payload for write success,
  validation errors, blocked operations, diagnostics, and vector refresh data;
- define model-visible top-level tools:
  - `query_memory`;
  - `ingest_memory`;
- define model-visible child-process/helper tools where needed:
  - `request_user_clarification`;
  - `update_memory_graph` inside ingestion/creation flows;
- define deterministic write tool interfaces for:
  - creating memory logs;
  - creating graph nodes;
  - creating graph relationships;
  - creating relationship states;
  - patching graph nodes through `graph_update`;
- add schema/tool-registration tests.

This wave should avoid a broad runtime rewrite. It creates the target contracts
and makes unsupported legacy dependencies visible.

### Wave 2: Deprecated Flow Cleanup

Goal: remove active legacy orchestration paths so wrong behavior fails visibly.

Scope:

- remove production use of deterministic chat runtime mode;
- remove `pending_process` as an agentic continuation mechanism;
- remove pending-process review from active runtime routing;
- remove model-visible pending-process tools such as
  `resume_pending_process`, `pause_pending_process`, and
  `cancel_pending_process`;
- remove `handoff_target` state switching from production agentic flow;
- remove facade-level `start_memory_ingestion` clarification/resume behavior
  from model-visible paths;
- remove correction-intake legacy routing if still active;
- keep only minimal persistence compatibility where existing migrations require
  it, with no production runtime dependency;
- rewrite or delete tests that expect pending-process/handoff behavior.

Temporary feature gaps are acceptable in this wave. Silent fallback behavior is
not acceptable.

### Wave 3: Nested Agentic Runtime Implementation

Goal: implement the target runtime using explicit nested frames and compact tool
results.

Scope:

- make `conversation_entry` expose only `query_memory` and `ingest_memory`;
- implement `query_memory` as a read-only child frame:
  - scoped semantic retrieval;
  - hydration of top hits;
  - answer generation from hydrated context;
  - no clarification tool;
  - compact result returned to parent;
- implement `memory_ingestion` as a child frame:
  - semantic top-k retrieval from source/history context;
  - hydration of retrieved graph context;
  - reasoning;
  - structured planning into `MemoryPlan` actions;
  - action execution through model-visible tools or child frames;
- implement `memory_creation` as a child frame:
  - receives history/context plus one `MemoryPlanAction`;
  - does not receive duplicated `source_text` when source is already in history;
  - calls deterministic creation/write tools;
  - receives structured validation errors as tool results;
  - lets the LLM decide retry, clarification, alternative tool call, or failure;
- use `graph_update` as the child frame for update actions;
- ensure clarification resumes the exact interrupted frame by appending the
  matching provider `tool` message;
- ensure child completion returns one compact result to the parent tool call;
- ensure deterministic writes refresh affected vector scopes behind the tool.

### Wave 4: Stabilization, Overview, And UAT

Goal: verify the new architecture and document the final behavior.

Scope:

- add end-to-end tests for:
  - query flow;
  - simple memory creation;
  - memory creation with clarification;
  - ingestion plan that calls `graph_update`;
  - structured validation error retry;
  - absence of pending-process/handoff runtime paths;
- update architecture diagrams and AI-engineering notes;
- reduce noisy frame/tool logs while keeping useful diagnostics;
- run manual UAT against the OpenAI client;
- confirm legacy hidden behavior is gone and unsupported flows fail visibly.

