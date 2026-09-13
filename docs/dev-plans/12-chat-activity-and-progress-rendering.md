# Chat Activity And Progress Rendering

## Goal

Give users a clear, refresh-safe view of what the assistant is doing while a
chat request is being processed.

The normal chat should communicate progress through short, human-readable
activity summaries. It must not expose session IDs, frame IDs, tool-call IDs,
provider payloads, raw prompts, internal state names, or private chain-of-thought.

The first activity vocabulary should be derived from the current agentic states
and ingestion pipeline steps. The vocabulary must remain extensible: states and
steps may be added, removed, renamed, grouped, or split without requiring the
frontend to understand backend implementation details.

## Product Outcome

While the assistant is working, the user sees:

- one prominent current activity;
- optionally the last two or three completed activity summaries;
- simple wording such as `Searching your memories` or `Checking for conflicts`;
- a clear waiting state when user input is required;
- stable progress after refresh or when returning to a chat.

When the request completes, the activity presentation is removed from the
normal conversation and only the final assistant message remains. Developer
trace details remain available only in the opt-in AI trace page.

## Architecture Position

This plan extends, but does not replace:

- [Chat Consumers, Conversation Runtime, And Backend Tool Facade](03-chat-interface-and-db-tooling.md)
- [Agentic Process Design And Definition](08-agentic-process-design.md)
- [Backend Ingestion Pipeline Definition](02-backend-ingestion-pipeline.md)

The conversation runtime owns the process lifecycle and public activity events.
The agentic runtime and ingestion pipeline report meaningful state or step
transitions to that lifecycle. Web and Telegram remain presentation adapters.

The public activity contract is separate from the developer trace contract:

```text
agentic state / ingestion step
              |
              v
public activity presentation registry
              |
              v
durable chat activity events and process snapshot
              |
       +------+------+
       |             |
       v             v
    web chat      Telegram
```

## Clarification Integration Audit

The first production-chat audit exposed a backend handoff gap rather than a
question-component rendering defect:

```text
web message
  -> ChatRuntime._call_agentic
  -> ingest_memory
  -> memory planning / graph update
  -> ask_clarification
  -> clarification agent
  -> pending question tool
  -> interrupted AgenticFrame + clarification_packet
  -> ChatResponse + web question component
```

The last two transitions are the required user-facing boundary. The current
chat ingestion branch creates `MemoryIngestionContext` from semantic
retrieval, but does not carry an active `RunReferenceRegistry` or registry
snapshot into that context. The child clarification frame therefore cannot
validate or project the refs supplied by the planning and graph-update states.
It returns an unresolved report, after which the parent may retry the
clarification handoff. The process can consequently remain `working` while
the browser receives neither a question packet nor a resumable frame.

The standalone interactive UAT path does not reproduce this failure because
its legacy ingestion flow explicitly creates and propagates the registry
before entering the clarification child frame. That makes it a useful
regression path, but not proof that the web chat contract is wired.

There is also a reference-contract mismatch to resolve before implementing the
production bridge:

- the newer agentic planning contracts expose readable refs such as
  `node_new_lorenzo` and carry them in `RefContext`;
- the clarification toolbox currently validates against the ingestion
  `RunReferenceRegistry`, whose generated refs are `NODE_000001` and whose
  proposal refs must be `CANDIDATE_*`;
- the agentic `GraphContextPackage` currently has aliases and candidate data,
  but no active registry snapshot.

The recommended delivery order is:

1. choose one model-facing ref contract and define a narrow adapter at the
   legacy graph/write boundary;
2. initialize and propagate that context through chat ingestion, every child
   frame, and persisted frame payloads;
3. make a pending clarification tool call terminate the current run as an
   interrupted frame, with a validated packet and no natural-language-only
   fallback;
4. verify the API response, session detail after refresh, answer submission,
   and resumed final response with one end-to-end chat test;
5. only then refine the frontend activity/question presentation and live
   process synchronization.

The frontend already follows the intended contract: it reads the packet from
the response or `active_agentic_frame`, hides transient clarification messages,
and renders `ClarificationQuestionBox` only when a structured packet exists.
Parsing a natural-language question in the frontend would conceal the backend
failure and would not support safe resume after refresh.

## Locked Product Principles

- Progress wording describes observable work, not hidden model reasoning.
- The backend resolves internal states and steps into safe user-facing titles
  and summaries.
- The frontend never renders a raw backend state or implementation identifier.
- Activity text is deterministic for a given activity occurrence; polling or
  re-rendering must not make the title flicker.
- Activity events are operational UI data, not conversation messages and must
  not enter model history.
- The final response is rendered as the normal assistant message only.
- Waiting for clarification is a first-class user state, not a generic error
  or an indefinitely spinning progress indicator.
- Unknown future states use a safe generic fallback and are observable through
  developer diagnostics without breaking the user experience.

## Presentation Registry

Create a backend-owned presentation registry keyed by a stable activity key.
The key may refer to an agentic state, an ingestion step, or a more specific
substep:

```text
activity key
  -> user-facing category
  -> 3-5 equivalent title variants
  -> short summary
  -> lifecycle behavior
```

The resolved activity event sent to clients contains the selected title and
summary, not the full title catalogue or the internal key. A stable occurrence
index or run seed selects a variant so that the title can vary between
occurrences without changing during polling.

### Initial agentic-state mapping

The initial registry should cover the current `AgenticStateId` values:

| Internal source | User-facing category | Example title variants |
|---|---|---|
| `conversation_entry` | Understanding the request | `Understanding your request`; `Getting oriented`; `Working out what you need` |
| `reasoning_checkpoint` | Considering the details | `Thinking this through`; `Considering the details`; `Working through the important points` |
| `planning_checkpoint` | Planning the work | `Planning the next steps`; `Organizing the work`; `Building a plan` |
| `memory_log_extraction` | Identifying meaningful memories | `Picking out meaningful details`; `Finding the key moments`; `Extracting memories` |
| `memory_query` | Searching memory | `Searching your memories`; `Looking through related memories`; `Finding relevant context` |
| `memory_ingestion` | Organizing what was shared | `Organizing what you shared`; `Preparing your memories`; `Structuring this information` |
| `memory_creation` | Saving memories | `Saving the selected memories`; `Adding this to your memory`; `Creating memory entries` |
| `graph_update` | Updating connections | `Updating your memory graph`; `Connecting related information`; `Applying the updates` |
| `contradiction_review` | Checking consistency | `Checking for conflicts`; `Comparing with existing memories`; `Making sure this fits` |
| `profile_duplication` | Reviewing profile context | `Checking your profile context`; `Reviewing saved preferences`; `Comparing profile details` |
| `clarification_agent` | Preparing a question | `Preparing a question`; `Checking what needs clarification`; `Putting together a quick question` |

The wording is illustrative and should be reviewed for the supported UI
language before implementation. The summary should be stable and factual, for
example: `Checking related memories and existing details before continuing.`

### Ingestion pipeline steps

Agentic states provide the first vocabulary. Explicit ingestion steps should be
added where a state is too broad to explain a meaningful user-visible change,
for example:

- preparing source context;
- planning memory actions;
- extracting memory-log drafts;
- resolving identities;
- validating proposed changes;
- writing approved graph changes;
- refreshing vectors or summaries.

These step keys must be owned by the ingestion process, not inferred from
frontend strings. If both a state and a step are available, the more specific
step presentation wins. Otherwise the state presentation is used.

## Public Contracts

Introduce channel-neutral contracts alongside the existing `ChatResponse` and
session contracts.

### Activity event

Conceptual shape:

```text
ChatActivityEvent
  sequence              transport cursor; never displayed
  status                started | completed | waiting | failed
  title                 resolved human-facing title
  summary               short safe explanation
  activity_group        understanding | memory | planning | checking | saving | waiting
  created_at
```

### Process snapshot

Conceptual shape:

```text
ChatProcessSnapshot
  status                idle | working | waiting_for_user | completed | failed | cancelled
  current_activity     ChatActivityEvent or null
  recent_activities    bounded list of completed events
  started_at
  updated_at
  resumable             boolean
```

Internal session, frame, and operation references may remain in storage and
transport metadata for authorization, correlation, and recovery. They must not
be used as user-facing labels.

## Delivery Waves

### Wave 0: UX and contract baseline

- Confirm the public vocabulary and supported language strategy.
- Define the activity registry and fallback behavior.
- Define which transitions are meaningful enough to publish.
- Define the terminal-state and stale-process behavior.
- Add contract examples for direct answers, memory queries, ingestion,
  clarification, failures, and refresh/reconnect.

### Wave 1: Backend activity lifecycle

- Add typed activity and process snapshot contracts.
- Add a durable activity store or relational activity records.
- Mark a process as working before agentic execution begins.
- Publish activity at agentic-state entry and completion.
- Publish more specific ingestion-step activity where available.
- Publish waiting, completed, and failed terminal updates.
- Add a heartbeat or stale timeout so interrupted local processes do not remain
  indefinitely marked as working.
- Resolve all user-facing wording through the presentation registry.

### Wave 2: Chat API and recovery

- Expose the current process snapshot and bounded activity history through the
  authenticated chat API.
- Support a cursor for polling from the last received event.
- Ensure a session ID exists before a long-running request starts, including the
  first message in a new chat.
- Prefer an accepted/background execution boundary for long-running work so the
  server owns the process if the browser refreshes or disconnects.
- Keep HTTP polling as the first transport because it fits the current local
  deployment; consider SSE after the contract and persistence behavior are
  stable.

### Wave 3: Frontend activity rendering

- Extract chat process synchronization into a reusable hook or controller.
- Replace local string arrays with the public process snapshot.
- Replace `ProcessingWidget` with a compact activity presentation showing the
  current step and a small recent history.
- Rehydrate activity after refresh and when selecting another chat.
- Keep activity state per session so another chat can continue processing in the
  background while the user reads the current chat.
- Replace developer-facing status text in the top bar and status bar.
- Remove activity immediately when the final assistant response is committed.
- Preserve a clear `Waiting for your answer` state while a clarification packet
  is active.

### Wave 4: Clarification integration

- Map `clarification_agent` and packet lifecycle to `Preparing a question` and
  `Waiting for your answer`.
- Keep the existing question component as the interaction surface.
- Rehydrate the question packet and progress after refresh.
- Render retry/recovery language without exposing error codes, frame IDs, or
  tool-call IDs.
- Verify that answering a question returns to the ordinary activity lifecycle
  before the final response is shown.
- Repair the production chat-to-ingestion registry handoff before changing
  frontend question rendering.
- Add a real chat API regression covering the same story as the interactive
  clarification UAT, including durable frame creation and resume.

### Wave 5: Quality and evolution

- Test unknown, renamed, and newly added states with the generic fallback.
- Test title stability across polling, refresh, reconnect, and chat switching.
- Add accessibility announcements for meaningful transitions without causing a
  screen-reader announcement on every heartbeat.
- Add localization-ready message keys while keeping resolved English copy in
  the initial MVP if that remains the chosen product language.
- Measure activity frequency and reduce noisy transitions.

## Files And Boundaries

Likely backend changes:

- `src/my_digital_brain/chat/models.py`
- `src/my_digital_brain/chat/runtime.py`
- `src/my_digital_brain/chat/store.py`
- `src/my_digital_brain/chat/relational_store.py`
- `src/my_digital_brain/api/routes/chat.py`
- new `src/my_digital_brain/chat/activity.py` or equivalent presentation module
- agentic runtime and ingestion runtime instrumentation points

Likely frontend changes:

- `frontend/src/types/chat.ts`
- `frontend/src/api/chat.ts`
- `frontend/src/views/ChatView.tsx`
- `frontend/src/features/chat/components/ChatMessageList.tsx`
- `frontend/src/features/chat/components/ChatStatusBar.tsx`
- `frontend/src/features/chat/components/ChatTopbar.tsx`
- new chat process/activity hook and activity component
- `frontend/src/styles.css`

Tests should cover backend contracts, registry fallback and variant stability,
runtime lifecycle transitions, API cursor behavior, refresh recovery, frontend
state transitions, accessibility announcements, and final-message-only
rendering.

## Deprecations And Cleanup

- Remove frontend-generated strings such as `Message sent`, `Waiting for
  backend processing...`, and `Response received: ...`.
- Retire `processUpdatesFromSession()` once server activity is authoritative.
- Stop using `isSending` as the source of truth for process state.
- Remove normal-user rendering of conversation IDs, agentic frame IDs, raw state
  names, error codes, and diagnostic metadata.
- Keep `ChatResponse.metadata`, compact traces, and detailed diagnostics for the
  developer trace and operational tooling.
- Review the legacy cancellation endpoint separately; it currently reports that
  cancellation is unavailable and should not be presented as an active product
  capability.

## Open Decisions

Recommended defaults are stated so implementation can proceed without blocking.

1. **Activity history while working:** show the current activity plus the last
   two completed summaries, then remove the activity view on completion.
2. **Chat switching:** allow switching while work continues; show a small
   per-chat working indicator in history.
3. **Transport:** use durable HTTP polling first, with SSE deferred until the
   contract is proven.
4. **Execution boundary:** use an accepted/background process for true refresh
   recovery; retain a compatibility path for synchronous local execution during
   migration.
5. **Variant selection:** select deterministically per activity occurrence, not
   randomly on each render.
6. **Copy style:** prefer natural descriptions of observable work. Avoid
   claiming that the product is exposing the model's private thoughts.
7. **Language:** make the registry localization-ready; confirm whether the MVP
   should ship English-only or support Italian copy from the start.

## Initial Success Criteria

- A user can submit a message and see meaningful progress tied to the actual
  agentic state or ingestion step.
- No progress label contains an internal ID or unexplained implementation term.
- Refreshing the page shows the correct current process state when work is still
  active or awaiting an answer.
- Switching chats does not lose or cancel another chat's visible process state.
- Clarification questions appear in a stable waiting state and resume correctly.
- The completed conversation contains only the final assistant response, with
  no transient activity transcript appended to chat history.
- Adding or renaming a backend state requires updating the registry and tests,
  not rewriting frontend state logic.
