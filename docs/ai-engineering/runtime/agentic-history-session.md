# Agentic history session

## Purpose and status

**Binding framework specification.** `AgenticHistorySession` is the centralized,
stateful history manager for one logical agentic conversation or process. The
orchestrator initializes it once, then passes it through direct state calls and
agent-as-tool calls.

It provides shared master-history continuity while keeping every LLM state’s
provider transcript local, valid, and disposable after completion. It does not
define domain workflow, prompt content, automatic summarization strategy,
automatic promotion, or an alternate tool-call loop.

This specification extends the [agentic state framework](agentic-state-framework.md)
and the [tool-calling protocol](tool-calling-protocol.md).

## Why one live session object

The object passed through an orchestration is a session, not a stateless helper.
It owns the relationship between a shared conversation and the state invocations
that temporarily use it. This avoids copying master history into every agent,
while preventing a child agent’s implementation details from leaking into its
parent’s provider transcript.

`AgenticHistorySession` is not a replacement for durable chat storage. The
orchestrator loads the relevant durable conversation history, initializes this
runtime object, and persists only the accepted durable changes and any required
paused-state snapshot through the appropriate storage boundary.

## History layers and ownership

| Layer | Typed object | Owner | Lifetime | Contents |
| --- | --- | --- | --- | --- |
| Durable conversation | typed conversation entries | chat storage | durable | User/assistant messages, question/answer interactions, and explicitly promoted compact model-only entries. |
| Shared master history | `AgenticHistorySession` | orchestrator-created runtime session | one logical orchestration | The selected chat-wide history available for projection to agentic states. |
| State-local history | `StateHistory` | one state run in `AgenticHistorySession` | one state invocation | The local LLM conversation assembled for that state. |
| Provider transcript | canonical session transcript owned through `LLMInterfaceCore` | LLM client/runtime | one state invocation or pause/resume | Exact role, assistant tool-call, and matching tool-output messages required by the provider. |
| Paused snapshot | canonical continuation/frame DTO | persistence boundary | only while awaiting input | The state-local provider transcript and minimum context needed to resume it. |

The state-local history and provider transcript may be represented by the same
typed transcript object when their semantics align. They must still have one
clear owner: the canonical client/runtime is the only component that appends
provider-protocol turns.

### Durable conversation projections

Durable conversation entries support two deterministic consumers without
becoming two stored histories. The frontend projection returns user-facing
messages and readable question/answer interaction items. The model-history
projection renders those same completed interactions as ordered assistant
question and user answer messages, and may additionally include an explicitly
promoted compact model-only entry. Raw tool calls, tool outputs, traces, and
reasoning artifacts belong to state-local runtime history and neither durable
projection.

The orchestrator loads a bounded model-history projection before constructing
`AgenticHistorySession`. The current user request is excluded from that
projection because `BaseAgenticState` appends it once. Question/answer pairs are
selected atomically so an answer is never detached from its question.

## Core objects

### `AgenticHistorySession`

One instance belongs to one orchestration. Its minimum responsibilities are:

- hold the shared master history and its revision;
- register active `StateHistory` records by `state_run_id`;
- create a state-local history by copying the history projection selected by
  the invoking caller;
- link child state runs to their `parent_state_run_id` and, when applicable, the
  parent provider call ID;
- accept explicit promotions to shared master history;
- retain a paused state snapshot or release a completed state-local history.

It must not generate provider call IDs, execute tools, choose tools, build
prompts, infer which content is worth promoting, or mutate a provider transcript
out of order.

### `StateHistory`

`StateHistory` represents one invocation of one configured agentic state. It
contains:

- `state_id`: the stable state type/configuration identifier;
- `state_run_id`: the unique invocation identifier;
- `parent_state_run_id`: the direct parent state run when the state was invoked
  by another state;
- `parent_provider_call_id`: the parent’s provider-issued tool-call ID when
  this invocation is an agent tool;
- the shared master-history revision at state start and the caller-selected
  projection copied into this state; the revision does not claim that every
  projected message came from master history;
- the local provider transcript or its canonical session reference; and
- lifecycle status sufficient to distinguish active, paused, and completed
  state runs.

`state_id` is not enough to identify an invocation: a state type can run many
times in one orchestration. The session must use `state_run_id` for parent/child
relationships and persistence.

### Master-history promotion

Adding content to shared master history is an explicit operation, conceptually:

```python
history_session.promote_to_master(
    origin_state_run_id=state_run_id,
    messages=selected_messages,
)
```

The caller decides which selected message or compact outcome is useful beyond
its local state. The history session records the origin and advances the master
revision. It does not automatically promote state reasoning, raw tool arguments,
tool outputs, traces, status messages, or a child’s full local transcript.

### Paused continuation

`PausedStateContinuationDTO` is the minimum persisted record for a state-local
provider transcript awaiting external input. It is not a second agentic-frame
framework and it does not own domain workflow.

It contains a copied `StateHistory` snapshot and the complete provider-call
batch: each call has either its completed success/error output or a typed
interaction request awaiting external input. Provider call IDs correlate
answers. The nested `StateHistory` is the single source for the run ID, parent
linkage, selected revision, and exact local transcript; those fields are not
duplicated on the continuation DTO.

The persistence boundary may map this continuation to a backend UUID, but it
does not expose that UUID to models or users. A clarification's
`clarification_ref` correlates its internal packet and later resolution; the
provider call ID continues to govern transcript pairing.

## Integration points

| Collaborator | Interaction with `AgenticHistorySession` |
| --- | --- |
| Orchestrator | Loads the durable history, creates the session, starts the root state, and persists explicit master-history changes or paused snapshots. |
| `BaseAgenticState` | Requests a new `StateHistory`, receives its local transcript, appends the configured invocation request once as a user message, then delegates to the client. |
| Invoking caller / parent state | Exposes a registered child state or workflow through its toolbox. The framework binds the active parent run and provider call; model-facing arguments contain only the tool's functional input. |
| `LLMInterfaceCore` / canonical runtime | Uses and appends the state-local provider transcript. It owns assistant tool-call and tool-output ordering and provider-call IDs. |
| Toolbox / agent tool handler | Receives the backend invocation context, obtains the default child projection from the shared history session, starts the linked child, and converts its result into one typed parent tool output. |
| Durable chat store | Stores typed conversation entries and supplies the frontend and model-history source material. It does not store arbitrary live runtime state as metadata. |
| Paused-frame persistence | Stores only an interrupted state’s typed continuation and minimum state-history linkage, keyed by `state_run_id`. |

No collaborator receives authority to modify another state’s local transcript.

## Functional lifecycle

### Root state

```text
orchestrator loads durable conversation
  -> creates AgenticHistorySession(master history)
  -> starts root StateHistory(state_run_id A)
  -> orchestrator selects the root state's history projection
  -> root state appends its invocation request as one user message
  -> client runs the local provider transcript for A
```

The root state may be an LLM agent or a deterministic caller. The history
session does not require the orchestrator itself to be an agent.

### Child agent invoked as a tool

```text
state A provider transcript
  user request -> assistant tool call (parent_provider_call_id)

tool handler
  -> starts StateHistory B in the same AgenticHistorySession
  -> framework projects B's conversational history from parent A
  -> B starts a new local transcript; it does not inherit A's raw tool call
  -> B appends its own invocation request as a user message
  -> B runs its client/tool loop
  -> B completes and returns a compact typed result
  -> B local history is released

state A provider transcript
  assistant tool call -> matching tool output -> next assistant completion/tool call
```

The registered handler receives a backend-only invocation context from the
framework. It identifies state A, the provider-issued parent call, and the
shared history session; none of those values are model tool arguments. The
history session creates B's default inherited projection from A's selected
conversational turns and current user message. It excludes A's system prompt,
open assistant tool-call turn, tool outputs, traces, and provider metadata.

The same inheritance applies when A invokes a deterministic workflow behind a
tool: the workflow receives the invocation context and supplies that inherited
projection to its AI states as needed. The workflow passes semantic results
through explicit DTOs; it never cascades one child state's raw transcript into
another.

The child may itself invoke other agents. Each invocation creates another
`StateHistory` linked by `parent_state_run_id`, while each provider transcript
remains local to its state run.

### Master update during a child invocation

```text
state B explicitly promotes selected content
  -> AgenticHistorySession updates shared master history, revision N -> N+1
  -> future state invocations can select revision N+1
  -> B returns compact result to A as the required tool output
  -> A resumes its existing transcript only after that matched output
```

Master-history updates are not copied into every open local transcript. In
particular, a new master message must never be inserted between a parent
assistant tool call and its matching tool output. The compact child tool output
is how an active parent learns what happened. Later state invocations can use
the newer master-history projection.

### Pause and resume

If a state awaits user input, its `StateHistory` is not released. Its mapped
tool's logical invocation remains open, but the current Python request returns
an `awaiting_input` continuation; it does not block waiting for a later UI
request. The orchestrator persists the canonical continuation plus the
state-run linkage. When input arrives, it reloads the same history session/state
run, validates the answers, and resumes only after every interaction in that
provider batch has an output. All outputs are appended together in provider
call order before one next provider request. A tool-handler failure does not
pause the batch: it is represented immediately by a matching error output. No
pending tool-result status is introduced. This is continuation of the same
logical invocation, not a second history flow.

For a paused child agent, only the deepest paused child owns the interaction
packet rendered to the user. Ancestor state runs retain their open parent tool
call and await the compact child result, but never create another clarification
packet or a second user-visible question. Once the child completes, its handler
returns one matched output to the parent and normal nested resumption continues.

## History selection and restriction

The application supplies a durable conversation projection when starting a
top-level state. A nested state or workflow inherits the invoking state's
selected conversational projection by default through the history session. A
specialized child may receive a deliberately restricted form plus its own
purpose-specific typed context, but it must not independently restart from
global master history.

This is selection, not copying or uncontrolled propagation. The history session
supplies the central source and records the selected master revision; the
concrete state defines the needed view. Do not introduce a generic policy
language, automatic context expansion, or automatic summarization subsystem
until a concrete accepted state requires it.

## Invariants

- One orchestration uses one shared `AgenticHistorySession`.
- Every state invocation has a unique `state_run_id`.
- Shared master history is centrally owned; state-local histories are not
  treated as master-history copies.
- A child never receives its parent’s raw provider tool-call transcript as its
  own local conversation.
- Nested agent and workflow handlers receive history through the framework
  invocation context, never through model-generated tool arguments.
- The client/runtime alone appends provider assistant/tool protocol messages.
- A completed child state releases its local history after returning its compact
  typed result; a paused state persists it only for continuation.
- Master promotion is explicit and records its originating state run.
- Existing open provider transcripts are never retroactively rewritten from a
  master-history update.
- A parent resumes only through the original matched provider tool output.

## Migration direction

The current `AgenticHistoryService` is useful source material but is not the
target ownership model: it combines durable-message synchronization, loose
metadata-backed master history, rendering, compaction, prompt projection, tool
summary, and finalization concerns. The target migration replaces those loose
history representations with the objects in this specification and removes
superseded paths as each caller moves.

Do not run a second history path beside `AgenticHistorySession`. Migrate one
caller/state at a time after the canonical session and agentic-state contracts
are implemented.
