# Project TODOs

This file tracks deferred work that is intentionally not part of the current
implementation slice. It should hold product-level follow-ups, not detailed
wave plans.

## Focused Agentic MVP Follow-Up

The first focused MVP slice has implemented the core agentic chat wiring,
tool-enabled ingestion planning, pending-process review entry point,
agent-invoked contradiction review handoff, and safe chat response rendering.

Remaining work in this file is intentionally future-facing and should not be
mixed into that MVP slice.

Potential follow-ups after hands-on usage:

- Decide whether `agentic` chat mode becomes the default runtime mode.
- Improve user-facing summaries after write-plan execution based on real UAT
  feedback.
- Add more evaluation examples for contradiction clarification wording.

## High Priority Agentic Fixes

These items are not broad future enhancements. They are required to keep the
implemented agentic runtime aligned with the locked architecture.

### Pending Process State Application

Status: implemented as the baseline lifecycle foundation.

- `PendingProcessStatus` supports `paused`.
- Chat pending storage supports one active pending process per session and a
  paused backlog with compact summaries.
- `pause_pending_process` clears active state, preserves a backend-only
  resumable snapshot, and keeps a compact model-facing pending summary.
- `cancel_pending_process` clears active state, marks the process cancelled, and
  marks the checkpoint non-resumable while preserving compact audit/chat
  summary.
- `resume_pending_process` accepts `pending_process_id` only. It uses the
  current message and recent history from runtime context instead of a
  `user_reply` argument.
- Memory-ingestion resume re-enters the ingestion service path, refreshes graph
  context, and reruns validation/resolution before write execution.
- `pending_process_review` receives active pending summary plus up to five
  paused summaries, without backend-only snapshots or noisy transport metadata.
- Ambiguous process selection returns verbose tool errors so the model can ask
  the user naturally.

Remaining follow-up after real usage:

- Decide whether a superseded active pending process should usually be paused or
  cancelled when the user starts unrelated work.

### State-Aware History Builder

Status: implemented as a reusable foundation.

- `AgenticHistoryService` is the dedicated history/context-building service;
  `ChatRuntime`, `AgenticStateRunner`, and `AgenticIngestionPlanner` use it
  instead of assembling model-facing history locally.
- User-visible chat persistence remains separate from internal agentic
  `ConversationContext` and neutral message history.
- Neutral internal messages are supported for user messages, assistant messages,
  assistant tool calls, tool outputs, compacted summaries, process handoffs, and
  pending-process summaries.
- State-specific history projections are centralized:
  - top-level states get full usable conversation history or compacted history;
  - specialist states get only the relevant parent history and process context;
  - nested tool/provider traces are compacted upward into concise tool outputs.
- Memory ingestion planning receives source text, usable conversation context,
  mention scan, compact graph context, current time/timezone, pending
  clarification answer when present, and prior relevant tool outputs.
- Backend-only channel/session metadata is removed from model-facing payloads
  unless a deliberate `ChannelContextProjection` is built.

### Planner Structured Output Refactor

Status: implemented in the planner foundation.

- `submit_extraction_plan` has been removed from the
  `memory_ingestion_planning` toolbox.
- `memory_ingestion_planning` can use support tools during execution and then
  returns a required structured final output.
- `memory_ingestion_planning` ends by returning a validated
  `ExtractionPlanDraft` structured output, not by calling a final submission
  tool.
- Backend enrichment deterministically converts the draft into the canonical
  `ExtractionPlan` by adding source provenance, task IDs, context package ID,
  and backend metadata.
- Keep planning tools for side work only:
  - `request_graph_context_expansion`
  - `request_contradiction_review`
- After the enriched `ExtractionPlan` is built, backend code
  deterministically routes the next process step from `execution_mode`,
  `tasks`, `clarification`, and `context_gaps`.
- Free-form assistant text alone must not be treated as a valid planning
  result.

### Structured Contradiction Review Output

- Status: implemented for the runtime and ingestion-planner detour.
- Contradiction clarification heuristics have been replaced with a structured
  judge result.
- The judge returns a validated `ContradictionJudgeResultContext` with a
  result intent.
- Supported contradiction result intents:
  - `needs_context`: continue the judge state with additional read-only graph or
    evidence context;
  - `needs_clarification`: ask the user before a final verdict;
  - `emit_verdict`: return a final contradiction decision and recommended
    backend action;
  - `fail_safe`: stop the branch and surface a safe error/uncertainty summary.
- A clarification-producing result must include:
  - provisional decision or uncertainty summary;
  - clarification question;
  - affected refs;
  - source refs;
  - blocking/non-blocking flag;
  - resume context for the next contradiction review turn.
- A verdict-producing result must include:
  - decision: `no_conflict`, `nuance`, `temporal_update`, `contradiction`, or
    `needs_clarification`;
  - severity;
  - reason;
  - recommended graph action;
  - inspected context refs.
- User-facing contradiction clarification should be rendered only from the
  structured result, not by checking whether assistant text contains a question
  mark.
- Runtime intent application:
  - `needs_context` returns a context-needed branch for the caller/owner to
    handle;
  - `needs_clarification` creates pending process context with the structured
    clarification question;
  - `emit_verdict` returns a compact verdict upward to the conversational
    owner;
  - `fail_safe` becomes a safe error branch.

### Final Assistant Message Ownership

Status: implemented for normal completion paths.

- User-visible final replies are owned by:
  - `conversation_entry` for normal completed processes;
  - `pending_process_review` when the conversation starts from an active pending
    process;
  - deterministic chat runtime handlers for optional developer/debug shortcuts
    such as `/status` and `/cancel`.
- `memory_query`, `correction_intake`, contradiction review, ingestion planning,
  and backend subprocesses return compact process/tool outputs upward by
  default instead of owning final public text.
- After non-interrupting specialist completion, the runtime appends one compact
  tool-output summary to the owner context and reruns the owner state with tools
  disabled.
- Deeper states may still produce user-visible clarification or confirmation
  questions when the process cannot continue safely without user input. Those
  are process interruptions, not completed top-level answers.
- Raw tool traces, graph payloads, UUID-heavy internals, and backend diagnostics
  remain hidden from user-visible responses.

### Tool Surface Ownership

Status: implemented.

- Keep explicit `/status` and `/cancel` as optional deterministic chat-runtime
  developer/debug shortcuts, not normal user-facing product flows.
- Normal users should cancel, skip, pause, resume, or ask status-like questions
  through natural language handled by `pending_process_review`.
- Keep `conversation_entry` model-visible tools limited to:
  - `start_memory_ingestion`
  - `query_memory_context`
  - `propose_memory_correction`
- Expose `cancel_pending_process` to `pending_process_review` only when a
  pending process exists and the model infers explicit cancellation or skip.
- Keep `get_conversation_status` as deterministic backend/chat behavior unless
  a later design explicitly promotes it to a model-visible tool.
- State configs, prompt text, and the tool registry have been aligned with this
  ownership policy.

## Real Provider Smoke Tests

- Add controlled OpenAI/Azure smoke tests after local behavior is stable.
- Validate provider acceptance of generated tool schemas.
- Validate tool-call loop behavior with one simple state/tool pair.
- Validate verbose tool errors steer model recovery.
- Validate model routing for default, smart, and reasoning state tasks.
- Keep these tests opt-in because they require real credentials and provider
  cost.

## Observability And LangSmith Tracing

- Integrate agentic runtime tracing with `src/my_digital_brain/ai/tracing.py`.
- Use LangSmith remote tracing when configured.
- Attach sanitized metadata for:
  - state id
  - model task
  - model route
  - conversation id
  - owner id
  - pending process id
  - ingestion session id
  - tool names
  - handoff targets
  - status and error codes
- Avoid storing raw personal memory text, contact details, or raw graph payloads
  in trace metadata.
- Persist compact traces locally enough to debug state transitions and tool
  failures without exposing noisy prompt internals.

## Medium Priority UX And Conversation Flow

- Transform clarification handling into a planning-question flow:
  - backend/process states produce a structured outbound question;
  - the question may include candidate answers/options plus free-text fallback;
  - web chat renders clickable answer chips/buttons when options are available;
  - selecting an option sends a normal chat message or structured answer payload
    back through the same pending-process review path;
  - agentic states still receive compact history and pending-process context,
    not raw UI widget state.
- Keep clarification UX natural: clicking a candidate answer is a convenience,
  not a rigid command-only path. Free text remains valid.
- Add per-chat item actions in the recent-chat sidebar:
  - use an overflow `...` menu on each chat row;
  - archive chats through the backend session status instead of hard deleting
    them;
  - hide archived chats from the default recent list.

## Post-UAT Hardening

- Review confirmation policy after real user testing.
- Tighten risky mutation behavior only after observing actual chat patterns.
- Add stricter safety checks if UAT shows agent over-eagerness.
- Add broader evaluation examples for ingestion, clarification, correction,
  contradiction review, and memory queries.
- Review privacy/trust behavior once real Telegram and web chat flows are used.
