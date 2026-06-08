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

### Memory Storage Reasoning And User-Related Data

Status: baseline reasoning checkpoint skeleton implemented; the dedicated
refinement baseline is locked in
[Ingestion reasoning refinement wave 1](dev-plans/10-ingestion-reasoning-refinement-wave-1.md).
Plug-in points, owner/user graph policy, and duplicate handling remain
high-priority implementation follow-ups.

- `reasoning_checkpoint` now exists as a reusable agentic state skeleton with:
  - purpose-specific reasoning guidelines in its input context;
  - caller-provided dedicated context plus optional conversation/history,
    compact graph context, prior tool outputs, current time/timezone, and model
    routing;
  - structured output for insights, clarification candidates, entity
    understanding, node-versus-metadata recommendations, storage hints, context
    gaps, and guardrails;
  - optional read-only graph/context tools and structured clarification
    interruption;
  - a thin `AgenticReasoningService` wrapper that can run it with the default
    result schema or a caller-provided Pydantic output schema.
- Build the matching reusable planning primitive before finalizing the wave-1
  ingestion split:
  - general planning system template;
  - purpose-specific planning guidelines;
  - caller-provided dedicated context;
  - optional conversation/history and prior tool-output context;
  - selected model route;
  - caller-provided structured output schema;
  - strict boundary: planning produces ordered process actions only, not
    candidates, validation, duplicate resolution, write plans, or mutations.
- Complete the contract-first documentation and implementation sequence:
  - lock docs for the contract/schema baseline;
  - implement lightweight LLM-facing draft contracts and backend-enriched
    handoff records;
  - add schema tests and exports only;
  - add context-rendering services for LLM-friendly payload views;
  - defer flow, agent, prompt, extraction, validation, and write orchestration
    until after the contract/modeling slice.
- Implement context renderers for `GraphContextPack` so model payloads receive
  only task-relevant views such as compact summaries, aliases, relationship
  snippets, duplicate hints, or missing-entity guidance.
- Lock alias handling in validation/write planning: aliases are extraction,
  retrieval, resolution, and context-building hints, not node identity and not
  automatically writable node properties.
- Decide where to plug the explicit reasoning/checkpoint step before crucial
  storage phases, especially before extraction task compilation, write-plan
  assembly, validation, and write execution.
- Apply the wave-1 ingestion refinement baseline:
  - retrieve whole-source hybrid graph context before reasoning;
  - compact it into a Graph Context Pack;
  - run structured reasoning before planning;
  - split entity planning/candidates from relationship planning/candidates;
  - stage entity creation until deterministic validation and duplicate handling
    have run;
  - plan relationships only from the resolved entity map.
- Reserve the duplicate-judge process slot before durable entity writes.
  Wave 1 keeps this deterministic and conservative; qualitative duplicate
  judging, user confirmation, merge application, metadata transfer, and
  re-embedding are later follow-ups.
- Analyze weird or low-quality storage behaviors from real traces and ingestion
  outputs, then adjust system prompts, structured contracts, validators, and
  write-plan compilation rules accordingly.
- Decide the owner/user modeling policy:
  - keep a canonical owner-specific graph node available for edgeable memories
    such as perceptions, relationship contexts, profile memories, and explicit
    owner-to-entity relationships;
  - keep owner scoping/provenance fields on memory-bearing nodes and sources so
    ordinary facts do not need noisy edges to the owner by default;
  - avoid burying user-specific facts in arbitrary metadata when they affect
    retrieval, correction, privacy, prompting, or graph traversal.
- Answer and codify: how do we allow user-related data storage?
  - durable traits, preferences, habits, communication style, and goals should
    become `ProfileMemory` records linked to the owner;
  - subjective views should become `Perception` records with user-stated versus
    inferred provenance and links to the perceived target;
  - meaningful relationships involving the owner should become
    `RelationshipContext` or typed relationships that can edge from the owner to
    the other entity;
  - ordinary events, claims, places, objects, and entities should keep source
    provenance and owner scope, while only adding explicit owner edges when the
    relationship itself is semantically useful.

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
- Memory ingestion context building is centralized. The current planner
  foundation used mention scan and compact graph context; the wave-1 refinement
  moves ingestion toward whole-source hybrid graph context, structured
  reasoning, entity planning, and relationship planning.
- Backend-only channel/session metadata is removed from model-facing payloads
  unless a deliberate `ChannelContextProjection` is built.

### Planner Structured Output Refactor

Status: implemented in the planner foundation. This remains useful as the
current structured-output foundation, but the target ingestion flow is now the
reasoning-first/entity-first refinement in
[Ingestion reasoning refinement wave 1](dev-plans/10-ingestion-reasoning-refinement-wave-1.md).

- `submit_extraction_plan` has been removed from the
  `memory_ingestion_planning` toolbox.
- `memory_ingestion_planning` can use support tools during execution and then
  returns a required structured final output.
- `memory_ingestion_planning` ends by returning a validated
  `SemanticIngestionPlanDraft` structured output, not by calling a final
  submission tool.
- Backend compilation deterministically converts the semantic draft into the
  canonical `ExtractionPlan` by choosing focused task schemas, adding source
  provenance, task IDs, context package ID, candidate/ref catalog policy, and
  backend metadata.
- Keep planning tools for side work only:
  - `request_graph_context_expansion`
  - `request_contradiction_review`
- After the compiled `ExtractionPlan` is built, backend code
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

## Retrieval Rendering Follow-Up

- Compare Otsu thresholding, knee detection, Jenks natural breaks, and small 1D
  clustering approaches for selecting which retrieval hits should drive graph
  workspace rendering.
- Keep agentic memory retrieval broader than UI graph rendering, then enrich
  answer context through graph context packages instead of narrowing the
  retrieval result too early.

## Observability And LangSmith Tracing

Status: baseline implemented.

- OpenAI/Azure clients are wrapped through `src/my_digital_brain/ai/tracing.py`
  when LangSmith is available.
- `@traceable` spans are applied to provider calls, agentic runtime states,
  ingestion planning/extraction, RAG retrieval/vectorization, Chroma vector
  operations, chat runtime handoffs, and memory tool facade operations.
- LangSmith remote tracing is controlled by environment configuration and stays
  disabled by default locally.

Remaining follow-up after real trace review:

- Attach richer sanitized metadata for:
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
- Review whether the existing local JSONL logs are sufficient as compact local
  traces, or whether a separate state-transition trace artifact is still useful.

## Medium Priority UX And Conversation Flow

- Structured clarification question flow is implemented as a baseline:
  - allowed agentic states call `request_user_clarification`;
  - backend stores a compact pending process plus a resumable snapshot;
  - web chat renders clickable options plus free-text answers;
  - structured answer packets are validated by the backend;
  - resumed states receive compact clarification-answer summaries, not raw UI
    widget state.
- Follow-up after usage: refine clarification option wording, multi-select
  behavior, and richer candidate-answer rendering.
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

## Embedding logics
right now we're embedding the whole node, but we need into account nodes updates or log activity. the good thing to improve at the same time with embedding retrieval could be to integrate a micro-embedding space: to have heavy vectors for ssmall text entries might be an overkill. we might prefer smaller embeddings for smaller phases,contexts to be logged. 
all the se micro embedding would indeed be redirected to the main node in the retrieval process, but the embedding portion is indeed smaller: more embedding entries but smaller even in size
