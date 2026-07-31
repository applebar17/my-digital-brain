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

Priority scale: `1` is highest priority and `5` is lowest priority. Priority
describes implementation urgency, not product importance. Implemented sections
remain documented for ownership and audit purposes but do not require a new
priority.

Potential follow-ups after hands-on usage:

Priority: 4

- Decide whether `agentic` chat mode becomes the default runtime mode.
- Improve user-facing summaries after write-plan execution based on real UAT
  feedback.
- Add more evaluation examples for contradiction clarification wording.

## Agentic And Ingestion Follow-Ups

These items are scoped follow-ups, ordered by the priority assigned to each
area. They keep the implemented agentic and ingestion runtimes aligned with
the locked architecture.

### Memory Storage Reasoning And User-Related Data

Status: baseline reasoning checkpoint skeleton implemented; the dedicated
refinement baseline is locked in
[Ingestion reasoning refinement wave 1](dev-plans/10-ingestion-reasoning-refinement-wave-1.md).
Plug-in points, owner/user graph policy, and duplicate handling remain
high-priority implementation follow-ups.
Priority: 1

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
- Use the wave-4 local UAT trace scripts during hands-on review to tune
  reasoning, planning, entity extraction, missing-entity handling, relationship
  extraction, and final candidate summaries.
- Continue hardening reasoning-first ingestion write behavior after UAT:
  validation quality, duplicate-judge integration, merge policy, and production
  orchestration polish.
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

### Typed Node Identity Fields

Status: deferred. The current implementation keeps the taxonomy unchanged and
uses `display_name` as the model-facing canonical identity field for node
resolution. Future taxonomy work should define optional type-specific identity
fields and retrieval behavior.
Priority: 2

- Add optional Person identity fields such as `given_name` and `family_name`
  without making a surname mandatory for mononyms or incomplete identities.
- Define type-specific canonical fields for Event, Place, Organization, Object,
  and other named node types instead of relying on one generic field everywhere.
- Define normalization and lookup behavior for full names, aliases, nicknames,
  compound surnames, and incomplete names.
- Extend candidate contracts, graph models, tool payload schemas, migrations,
  identity lookup, context rendering, and tests together.
- Preserve `display_name` as the universal human-readable rendering field even
  after structured identity fields are introduced.
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

### Identity Resolution And Context Packets

Status: foundation implemented; cross-scenario hardening remains.
Priority: 1

- Audit deterministic lookup and bounded context hydration for exact, multiple,
  fuzzy-only, and no-candidate results.
- Consolidate all model-facing reference formats behind the single uppercase,
  run-scoped registry. Reject invented, stale, cross-run, and cross-graph refs.
- Verify that every resolution step receives the correct candidate packet and
  relevant references outside the current batch without exposing graph IDs.
- Test duplicate-risk flows after clarification: attach to an existing node,
  create a new node, or keep the ambiguous name when the user has not asked to
  discard it.
- Revalidate references and graph state after clarification and before write
  execution, including concurrent graph changes.
- Keep the current decision boundary: the backend searches, validates, and
  writes; the LLM selects the semantic action from supplied context.

### Owner Profile Retrieval And Approval

Status: design and baseline contracts implemented; end-to-end policy follow-up.
Priority: 2

- Verify that generic retrieval exposes only the minimal `OWNER` identity
  snapshot, while profile data is loaded only for explicit profile purposes.
- Complete approved-only profile retrieval for stable or user-confirmed
  memories linked to the canonical owner.
- Keep confirmation and rejection backend-owned, including promotion to
  `prompt_allowed`, hidden-by-default proposals, and owner scoping.
- Trigger profile vector refresh when approval changes eligibility; exclude
  hidden, temporary, inferred-unconfirmed, archived, and confirmation-required
  profile memories.
- Test personality-duplication consumers as read-only users of the approved
  snapshot, with no graph-write capability.

### Clarification Contract And User Experience

Status: implemented through Wave 2. The canonical handoff, channel-neutral
packet, read-only clarification toolbox, grouped continuation, and semantic
question tools are active. Wave 3 owns persistent master-history promotion and
child-session retention.
Priority: 1

- Continue refining the typed clarification request with:
  - a clarification kind, target refs, question, reason, and evidence refs;
  - response modes such as `free_text`, `single_choice`, `multi_choice`,
    `confirmation`, and `free_text_or_audio`;
  - optional model-facing option refs, labels, short summaries, and a clear
    `other`/custom-answer capability;
  - channel-neutral answer fields for selected options, text, and audio
    transcription or attachment references.
- Support the no-match identity scenario: ask an open clarification without
  graph options, for example: `Who is Amos? Provide the full name or a detail
  that distinguishes him.` Allow typed or audio answers.
- Support the duplicate-risk scenario: present existing candidate names and
  compact summaries as selectable options plus an `Other` free-text choice,
  for example: `Amos Bianchi`, `Amos Rossi`, `Other`.
- Add and test additional UX scenarios:
  - missing attribute: ask for one structured field such as surname, city, or
    date;
  - confirmation: ask whether a proposed event, place, or relationship should
    be stored;
  - contradiction/correction: show the current value and the proposed value;
  - multi-participant or multi-target selection when one answer affects several
    refs;
  - temporal or place disambiguation with suggested values and custom input;
  - explicit discard/defer, available only when the user requests it.
- Keep graph IDs internal. Option refs must be model-facing registry refs and
  must resolve through the active run/graph registry before use.
- Keep clarification semantics centralized while allowing frontend, Telegram,
  and terminal channels to render different controls. Wave 3 owns promotion of
  clean question/answer pairs to the persisted master history; tool output and
  internal traces remain in the active LLM-session transcript.
- Align the web, Telegram, and terminal consumers with the canonical Wave 1
  packet and answer fields. Web keeps a packet locally for back/edit navigation
  and submits it once; Telegram and terminal submit one answer at a time.
- Return structured clarification API errors with stable codes and retry
  metadata for stale, mismatched, empty, and invalid answers.
- Defer browser media capture, media upload/storage, and transcription
  integration until a later clarification-media wave.
- Preserve the complete `ClarificationResolutionReport` through child,
  parent, and nested parent tool outputs. Derived resolved-answer lists must
  not replace the report as the source of truth.
- Define validation and rendering behavior for empty answers, invalid option
  refs, stale packets, repeated questions, audio-only answers, and answers that
  do not resolve the target.
- Add contract, serialization, channel-rendering, and end-to-end tests for all
  clarification kinds. Do not add deterministic identity decisions to the
  backend as part of this work.

### Place Search And Geocoding

Status: deferred. Place candidates currently rely on extracted names and do not
have a dedicated enrichment flow.
Priority: 3

- Add a backend-owned place-search tool that accepts a candidate name and
  optional city, country, source context, and user-provided hints.
- Return deterministic place candidates from the selected provider with a
  provider place ID, canonical name, formatted address, city, country,
  latitude, longitude, Google Maps URL, and provider metadata.
- Never let the LLM invent a maps URL or coordinates. The LLM may select one
  supplied result, request clarification, or keep the place unresolved.
- Define provider configuration, rate limits, caching, provenance, confidence,
  and behavior when providers return no or multiple matches.
- Store only approved enrichment on the Place node and retain the original
  user wording and lookup evidence for correction and re-resolution.
- Add tests for no match, one match, multiple matches, invalid provider data,
  coordinate validation, URL construction, idempotency, and cross-graph scope.

### Node-Media Linking Audit

Status: deferred. Review the current media/source contracts and graph write
paths before adding new media behavior.
Priority: 4

- Audit `MediaAsset`, source records, media-derived artifacts, and existing
  node-media relationship types for one consistent ownership model.
- Define whether media is linked directly to nodes, through Source, or both,
  and when each link is created during ingestion.
- Lock link properties such as role, evidence span, confidence, provenance,
  extraction run, ordering, lifecycle, visibility, and idempotency key.
- Verify support for one media asset linked to multiple nodes and one node
  linked to multiple media assets without duplicate edges.
- Check retrieval and vectorization behavior for media-linked nodes, including
  archived, private, derived, and transcription-only media.
- Add graph migration, write-plan, retrieval, permission, and end-to-end tests
  before changing node-media persistence behavior.

### Agentic Frame Continuation Cleanup

Status: active continuation is AgenticFrame-based. Legacy pending-process
storage, models, and routing have been removed from production code.
Priority: 2

- Keep clarification continuation represented as an interrupted `AgenticFrame`
  with grouped pending provider tool calls when a parallel batch is active.
- Resume by appending one matching provider `tool` message for every pending
  call to the saved frame history.
- Keep parent frames in `waiting_child` while child frames ask clarification.
- Keep user-facing clarification UI separate from normal chat bubbles.
- Do not reintroduce pending-process lifecycle concepts, review states, pause,
  resume, or cancel tools.

### State-Aware History Builder

Status: implemented as a reusable foundation.
Remaining history-projection and cross-channel audit: Priority 2.

- `AgenticHistoryService` is the dedicated history/context-building service;
  `ChatRuntime` and `AgenticStateRunner` use it instead of assembling
  model-facing history locally.
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
- Refactor `AgenticStateRunner.run_state` and `run_structured_state` message
  rendering so live agent calls receive a proper role-preserved conversation
  shape:
  - conversation history should be rendered as prior user/assistant messages or
    a compact history summary, with the latest user message represented once as
    the current message;
  - process-specific context should be rendered as concise, human-readable
    system/context sections instead of a large JSON-wrapped `context` user
    message;
  - structured-output calls should follow the same history/current-message
    policy while still passing the required output schema to the provider;
  - backend-only metadata, IDs, transport fields, and raw tool traces should
    remain excluded unless a state explicitly asks for a compact diagnostic
  view.
- Add a future context-compaction service/function that activates after a
  configurable provider-context threshold, preserves recent messages and
  important clarification exchanges, and emits no backend metadata. This is
  intentionally outside the current implementation wave.

### Contextual Tool Handoff Audit

Status: message-delta foundation implemented; audit remains required after the
ingestion runtime promotion.
Priority: 2

- Provider chat results now expose state-local `message_delta` entries produced
  during a tool loop: assistant `tool_calls`, matching `tool` outputs, and final
  assistant messages.
- Agentic state results carry that delta alongside compact `AgenticToolEvent`
  records. Tool events remain useful for diagnostics and routing; message deltas
  are the provider-compatible conversation record.

- Audit all agentic states and backend tools for the locked handoff rule:
  every state/tool starts, completes, returns one compact tool output to its
  invoker, and the invoker appends that output before the next state invocation.
- Normalize remaining internal subprocess handoffs so state-local message
  deltas are kept for trace/replay while only one compact tool output is passed
  upward to the invoking state.
- Deterministic processes should return structured activity logs with status,
  important operations, errors, refs, and next action.
- LLM-backed subprocesses should return their final assistant/process result
  after internal iteration, not raw nested traces.
- Internal handoffs may include technical context needed for guidance and
  guardrails; user-facing handoffs must stay human-friendly and non-technical.
- Refactor any remaining code paths that still pass backend state directly as
  fake conversation content or expose noisy internal traces to top-level model
  history.

### Unified LLM Session Verification

Status: canonical `run_session()` abstraction implemented; provider and
cross-channel verification remain.
Priority: 2

- Run controlled OpenAI/Azure checks for text, structured output, tool loops,
  structured-output repair, nested sessions, and pending clarification resume.
- Verify the configurable session tool budget, including complete multi-call
  batches and toolbox removal only on the next provider turn.
- Confirm that agentic, ingestion, resolution, chat, and UAT consumers use the
  unified session entrypoint and that removed generation entrypoints do not
  return through compatibility wrappers.
- Validate provider acceptance of generated tool schemas, verbose tool-error
  recovery, and model routing for default, smart, and reasoning tasks.
- Keep real-provider checks opt-in because they require credentials and incur
  provider cost.

### Prompt Inventory And Cleanup

Status: active prompts are code-managed constants mirrored to the file-backed
`PromptRegistry` templates for compatibility. See
`docs/ai-engineering/prompt-inventory.md` for state ownership.
Priority: 2

- Active runtime state prompts:
  `conversation_entry`, `memory_query`, `memory_ingestion`,
  `memory_node_planning`, `memory_log_planning`, `memory_edge_planning`,
  `memory_creation`, `graph_update`, `contradiction_review`,
  `reasoning_checkpoint`, and `planning_checkpoint`.
- Removed prompt surfaces:
  `pending_process_review`, `correction_intake`, `correction_proposal`,
  `ingestion_planner`, `query_retrieval_planning`, `profile_memory_extraction`,
  `maintenance_review`, `clarification_classifier`, and `answer_generation` are
  not production prompt owners. Do not load them from runtime code.
- Keep prompt files, state configs, contracts, and real runtime invocation paths
  aligned. Do not add a second active prompt family when replacing a flow;
  update the current prompt or delete the obsolete one.

### Ingestion Runtime Cleanup Audit

Status: planner-first runtime was removed in favor of the reasoning-first
`IngestionService`. Keep this audit item open until the next full review.
Priority: 2

- Verify no prompt, test, script, or docs path still describes the old
  mention-scan-first ingestion planner as active runtime behavior.
- Verify focused extraction, entity planning, relationship planning, missing
  entity planning, resolution, write-plan validation, graph write, and vector
  refresh are the only production ingestion chain.
- Free-form assistant text alone must never be treated as a valid planning or
  storage result.

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

Status: implemented for frame-based normal completion paths.

- User-visible final replies are owned by `conversation_entry` after child
  frames return compact tool results.
- `memory_query`, `memory_ingestion`, `memory_creation`, `graph_update`, and
  contradiction review return compact process/tool outputs upward by default
  instead of owning final public text.
- After non-interrupting specialist completion, the runtime appends one compact
  tool-output summary to the owner context and reruns the owner state with tools
  disabled.
- Deeper states may interrupt for clarification through AgenticFrame/tool-call
  continuation; clarification UI is not a completed top-level answer.
- Raw tool traces, graph payloads, UUID-heavy internals, and backend diagnostics
  remain hidden from user-visible responses.

### Tool Surface Ownership

Status: implemented for the frame-based runtime.

- `conversation_entry` model-visible tools are limited to:
  - `query_memory`
  - `ingest_memory`
- `query_memory` starts a read-only child frame; it does not ask clarification.
- `ingest_memory` starts the reasoning, planning, and action-frame ingestion
  flow; source content comes from frame history, not a tool argument.
- `update_memory_graph` is available to child states that need update behavior,
  not as a top-level conversation-entry tool.
- Pending-process tools, `start_memory_ingestion`, `query_memory_context`, and
  correction-specific production tools are legacy/inert surfaces and must not be
  reintroduced as active routing.
- State configs, prompt text, and the tool registry must stay aligned with this
  ownership policy.

## Retrieval Rendering Follow-Up

Priority: 4

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
Priority: 3

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

## UX And Conversation Flow

Priority: 4

- Structured clarification question flow is implemented as a baseline:
  - allowed agentic states call the centralized clarification tool;
  - the active `AgenticFrame`/LLM-session continuation holds the resumable
    snapshot;
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

Priority: 3

- Review confirmation policy after real user testing.
- Tighten risky mutation behavior only after observing actual chat patterns.
- Add stricter safety checks if UAT shows agent over-eagerness.
- Add broader evaluation examples for ingestion, clarification, correction,
  contradiction review, and memory queries.
- Review privacy/trust behavior once real Telegram and web chat flows are used.

## MemoryLog Vectorization And Node Update Flow

Status: design captured in
[MemoryLog vectorization and node update flow](dev-plans/11-node-log-vectorization-and-update-flow.md).
Priority: 3

Follow-up implementation work:

- Add first-class semantic `MemoryLog` records instead of hiding short updates in
  node metadata.
- Add support for multiple host links with one primary host and involved-target
  links.
- Add `MediaAsset` node/edge support for media attachments.
- Add micro-log vector scope using the shared v1 `512`-dimension embedding
  configuration, hydrating back to host/canonical domain nodes.
- Add agentic node-update tooling that writes `MemoryLog` records, safe patches,
  and vectors through deterministic backend guardrails.
- Low priority: design node summary refresh based on recent logs and important
  context changes, then refresh node-summary embeddings when derived summaries
  change.
