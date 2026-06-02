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

- Implement real backend handling for `resume_pending_process` and
  `pause_pending_process`.
- When a pending process is resumed, route the user reply back into the owning
  process with the original pending context and relevant conversation history.
- When a pending process is paused, clear it as the active pending process but
  preserve a compact unresolved-process summary for later context.
- When a new memory/query/correction supersedes a pending process, decide
  whether the old process should be paused, cancelled, or preserved in a pending
  backlog.
- Avoid rigid clarification forcing: pending context should guide
  `pending_process_review`, not deterministically consume every next message.

### State-Aware History Builder

- Create a dedicated history/context-building service instead of assembling
  model-facing history directly in `ChatRuntime` or individual process classes.
- Separate user-visible chat history from internal agentic history.
- Preserve neutral internal messages: user messages, assistant messages,
  assistant tool calls, tool outputs, compacted summaries, process handoffs, and
  pending-process summaries.
- Build state-specific history projections:
  - top-level states get full usable conversation history or compacted history;
  - specialist states get only the relevant parent history and process context;
  - nested tool/provider traces are compacted upward into concise tool outputs.
- Ensure memory ingestion planning receives source text, usable conversation
  context, mention scan, compact graph context, current time/timezone, pending
  clarification answer when present, and prior relevant tool outputs.
- Keep backend-only channel/session metadata out of model-facing history unless
  a deliberate `ChannelContextProjection` is built.

### Planner Structured Output Refactor

Status: implemented in the planner foundation.

- `submit_extraction_plan` has been removed from the
  `memory_ingestion_planning` toolbox.
- `memory_ingestion_planning` can use support tools during execution and then
  returns a required structured final output.
- `memory_ingestion_planning` ends by returning a validated `ExtractionPlan`
  structured output, not by calling a final submission tool.
- Keep planning tools for side work only:
  - `request_graph_context_expansion`
  - `request_contradiction_review`
- After the structured `ExtractionPlan` is returned, backend code
  deterministically routes the next process step from `execution_mode`,
  `tasks`, `clarification`, and `context_gaps`.
- Free-form assistant text alone must not be treated as a valid planning
  result.

### Structured Contradiction Review Output

- Replace contradiction clarification heuristics with a structured judge result.
- The judge should return a validated context such as
  `ContradictionJudgeResultContext` or a dedicated wrapper that includes a
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

### Tool Surface Ownership

- Keep explicit `/status` and `/cancel` as deterministic chat-runtime
  shortcuts.
- Keep `conversation_entry` model-visible tools limited to:
  - `start_memory_ingestion`
  - `query_memory_context`
  - `propose_memory_correction`
- Expose `cancel_pending_process` to `pending_process_review` only when a
  pending process exists and the model infers explicit cancellation or skip.
- Keep `get_conversation_status` as deterministic backend/chat behavior unless
  a later design explicitly promotes it to a model-visible tool.
- Refactor state configs/tool registry to match this ownership policy.

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

## Post-UAT Hardening

- Review confirmation policy after real user testing.
- Tighten risky mutation behavior only after observing actual chat patterns.
- Add stricter safety checks if UAT shows agent over-eagerness.
- Add broader evaluation examples for ingestion, clarification, correction,
  contradiction review, and memory queries.
- Review privacy/trust behavior once real Telegram and web chat flows are used.
