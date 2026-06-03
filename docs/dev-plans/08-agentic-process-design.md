# Agentic Process Design And Definition

## Goal

Implement the agentic process foundation that sits between chat consumers and
backend domain services.

The canonical behavior model lives in
[Agentic orchestration architecture](../architecture/agentic-orchestration.md).
This file is the implementation roadmap derived from that architecture and from
the [AI engineering principles](../ai-engineering/README.md).

The implementation direction is foundations first, wiring last:

1. Typed context objects.
2. Neutral conversation message protocol.
3. Prompt registry and prompt templates.
4. Agentic state configuration.
5. Tool-call/message routing protocols.
6. Query, correction, judge, profile, and maintenance process protocols.
7. Runtime wiring into chat once contracts are stable.

## Expected Output

This plan produces implementation artifacts and process specifications that can
be tested before full autonomous behavior is enabled.

Expected artifacts:

- Agent responsibility definitions.
- Behavioral protocols.
- Allowed and forbidden tools per agent/process.
- Input context requirements.
- Tool argument/result contracts and structured output contracts for focused
  LLM procedures.
- State handoff tables aligned with the canonical architecture.
- Clarification rules.
- Confirmation rules.
- Error and retry policies.
- Model routing policy by task difficulty.
- Privacy and provider-boundary rules.
- Evaluation examples for each process.

The final output is both code and behavioral contracts. Code should implement
stable contracts first; model-backed behavior can then be layered on top without
changing the domain services.

## Architecture Position

```text
Chat consumers
Telegram, web chat, future mobile
        |
        v
Conversation runtime
normalization, full usable history, pending process context
        |
        v
Agentic process layer
router, ingestion, query, correction, clarification, judge, profile
        |
        v
Backend domain services
ingestion, graph, AI provider, storage, vector
        |
        v
Databases and external providers
Neo4j, relational DB, Chroma, files, OpenAI/Azure
```

The agentic process layer is not the same as:

- chat adapters
- graph services
- ingestion storage execution
- provider SDK wrappers

It decides how to use those capabilities in a controlled conversational flow.

## Relationship To Other Plans

- [Chat consumers and runtime](03-chat-interface-and-db-tooling.md) wires Telegram/web chat to backend tools.
- [Backend ingestion pipeline](02-backend-ingestion-pipeline.md) provides structured extraction, validation, resolution, and write-plan execution.
- [AI provider foundation](07-ai-provider-foundation.md) provides LLM, structured generation, speech-to-text, embeddings, and routing abstractions.
- [LLM integration](../external-integrations/llm-integration.md) defines model usage boundaries and structured-output principles.
- [AI engineering principles](../ai-engineering/README.md) define the engineering rules this plan must follow.

This plan defines how agents and subprocesses behave when using those pieces,
and which implementation artifacts must exist for each wave.

## Locked Principles

- Agents choose actions and propose parameters; backend services validate and execute.
- Agents do not directly mutate graph, relational storage, files, or vectors.
- Top-level conversational action space stays small:
  - default answer path
  - `start_memory_ingestion`
  - `query_memory_context`
  - `propose_memory_correction`
- Subprocesses may have narrower internal toolboxes, but those must be explicitly designed.
- Tool descriptions, schemas, enum values, and errors are prompt surface.
- Agent behavior must be dynamic, but bounded by deterministic guardrails.
- Context packages must be low-noise and task-specific.
- Context objects must be explicit implementation contracts. After an action,
  tool, or subprocess finishes, it should produce the context object required by
  the next state or process instead of passing raw internal execution data.
- Internal UUIDs should be replaced with scoped aliases in model-facing contexts.
- Tool errors must be verbose enough to guide model recovery.
- Conversation history is part of context building, but it should be scoped or summarized instead of copied blindly into every call.
- Pending process state is contextual guidance, not deterministic routing. It should help agents resume work when appropriate without blocking a natural conversation.
- Clarification handling should preserve a normal chat feel. A later user message can be classified as clarification answer, new memory, question, correction, cancellation, or normal chat based on context.
- Orchestrator-like agentic states should return either a normal assistant
  message or a model-visible tool call. The tool call is the structured routing
  decision; no separate router decision object is required in the baseline.
- Clarification questions are normal assistant messages. Optional lightweight
  intent classification may be used to decide whether a later reply resumes the
  pending process, but this must not become a heavy clarification workflow.
- Clarifications should be user-friendly and sparse enough to avoid fatigue.
- Risky graph mutations require confirmation or conservative fallback.
- Foundation waves should implement contracts, context objects, prompt
  scaffolding, state configuration, and protocols before real autonomous
  behavior. Runtime wiring comes after these pieces are stable.
- The neutral conversation message protocol for this product is:
  user message, assistant message, assistant tool call, tool output, and
  compacted summary.
- `ChannelSessionMetadata` may be passed to backend states as optional runtime
  context, but model-facing prompts should not receive it for now. If a model
  needs channel details later, the backend must create a deliberate
  `ChannelContextProjection`.

## Canonical Architecture Design

The agentic state architecture, Mermaid handoff diagrams, state/tool matrix, and
prompt scaffolding baseline live in
[Agentic orchestration architecture](../architecture/agentic-orchestration.md).

This development plan should only track implementation waves derived from that
architecture document. The implementation sequence is foundations first, wiring
last: build typed contracts and prompt/state infrastructure before connecting
real model behavior into the chat runtime.

## Current Implementation State

Implemented foundation artifacts:

- `src/my_digital_brain/agentic/`
  - neutral conversation messages
  - context objects
  - state ids and agentic enums
  - Wave 1 state configuration
  - deterministic fallback router
  - Wave 2 memory query state configuration
  - deterministic memory query foundation service
  - Wave 3 correction and contradiction state configuration
  - correction, confirmation, contradiction judge, profile memory, and
    maintenance context contracts
  - agentic tool registry, state-specific toolbox factory, and backend binding
    layer under `src/my_digital_brain/agentic/tools/`
  - `memory_ingestion_planning` state configuration
  - provider-neutral runtime contracts:
    - `AgenticToolEvent`
    - `AgenticStateRunResult`
    - `AgenticRunResult`
    - `AgenticStateInvocation`
  - `AgenticStateRunner` for executing one configured `AS` state with prompt,
    model route, model-facing context payload, state toolbox, and tool mapping
  - `AgenticRuntime` for bounded multi-state execution and handoff inspection
- `src/my_digital_brain/prompts/`
  - file-backed prompt registry
  - templates for `conversation_entry`, `pending_process_review`, optional
    `clarification_classifier`, `memory_query`, `query_retrieval_planning`, and
    `answer_generation`
  - templates for `correction_intake`, `correction_proposal`,
    `contradiction_review`, `profile_memory_extraction`, and
    `maintenance_review`
  - template for `ingestion_planner`
- `tests/test_agentic_foundation.py`
  - neutral message validation
  - context payload safety
  - default state toolbox checks
  - prompt registry loading/rendering
  - deterministic router behavior
- `tests/test_agentic_query_foundation.py`
  - memory query state configuration
  - query prompt template loading
  - no-graph fallback behavior
  - graph seed resolution
  - `AnswerContext` and `ToolResultContext` construction
- `tests/test_agentic_risk_foundation.py`
  - correction and contradiction state toolbox checks
  - Wave 3 prompt template loading
  - confirmation-aware correction proposals
  - grounded contradiction judge results
  - profile memory and maintenance review contracts
- `tests/test_agentic_tool_bindings.py`
  - every configured state tool has a registered spec
  - state-specific toolboxes expose only allowed tools
  - top-level chat tools return handoff commands
  - read-only graph tools
  - proposal-only correction tools
  - verbose missing-dependency errors
- `tests/test_agentic_runtime.py`
  - direct assistant response from `conversation_entry`
  - query handoff into `memory_query`
  - correction handoff into `correction_intake`
  - pending context starts from `pending_process_review`
  - missing dependency tool errors do not crash the state
  - ingestion handoff delegates to backend facade
  - transition limit stops runaway handoffs
- `src/my_digital_brain/ai/`
  - `ToolCallingLLMProvider`
  - OpenAI/Azure provider support for `generate_chat_with_tools(...)`
  - fake provider support for runtime tests
  - agentic model routing defaults for smart/reasoning states

Implemented focused MVP integration artifacts:

- Opt-in `agentic` mode in `ChatRuntime`.
- Optional deterministic `/status` and `/cancel` developer/debug shortcuts
  still bypass the agentic runtime. They are not normal user-facing product
  flows.
- `ConversationContext` construction from persisted chat history, current
  message, current time/timezone, and active pending process context.
- `AgenticToolExecutionContext` construction from backend facade, graph
  service, ingestion service, chat store, session metadata, history refs, and
  pending process context.
- User-visible rendering from `AgenticRunResult` to `ChatResponse`.
- Assistant message persistence for agentic responses.
- Pending process persistence when agentic execution returns a clarification or
  pending-process hint.
- `AgenticIngestionPlanner`, which runs the tool-enabled
  `memory_ingestion_planning` support state and then requires a structured
  `ExtractionPlan` final output.
- Current planning-time support tools:
  - `request_graph_context_expansion`
  - `request_contradiction_review`
- Agent-invoked contradiction review handoff from planning contexts without
  deterministic contradiction detection rules.
- Contradiction review returns structured result intents instead of relying on
  free-form assistant text for clarification handling.
- `conversation_entry` model-visible tools are limited to memory ingestion,
  memory query, and memory correction.

Still intentionally deferred:

- Real OpenAI/Azure smoke tests.
- Prompt tuning and evaluation beyond local scripted behavior tests.
- LangSmith/remote tracing for agentic state runs and tool events.
- Post-UAT hardening of confirmation, clarification, and default runtime
  policies.

Deferred follow-ups are tracked in [Project TODOs](../todos.md).

## Agent And Process Catalog

### Conversation Router

Purpose:

Decide whether a user message should be answered directly or routed into a
top-level process.

Possible actions:

- default answer path
- `start_memory_ingestion`
- `query_memory_context`
- `propose_memory_correction`

Optional deterministic developer/debug shortcuts:

- `/status`
- `/cancel`

Locked behavior:

- When no active pending process exists, `conversation_entry` is the default
  entry state.
- When an active pending process exists, `pending_process_review` is the
  preferred entry state.
- Orchestrator-like states return either an assistant message or a model-visible
  tool call.
- The tool call is the structured routing decision.
- `conversation_entry` model-visible tools are limited to memory ingestion,
  memory query, and memory correction.
- `cancel_pending_process` belongs to `pending_process_review` when a pending
  process exists and cancellation/skip is inferred.
- Normal users should express cancel, skip, pause, or status-like questions in
  natural language; `pending_process_review` decides the action from context.
- The deterministic fallback router is already implemented for Wave 1.

Deferred decisions:

- When to enable real model-backed routing in the chat runtime.
- Whether model-backed routing should run before or after deterministic command
  shortcuts.
- Which evaluation examples are sufficient before enabling model-backed routing.

### Memory Ingestion Process

Purpose:

Coordinate memory-writing behavior over the existing ingestion pipeline.

Responsibilities:

- Build source context.
- Decide whether to run ingestion immediately or ask clarification first.
- Interpret ingestion outcomes.
- Present ingestion summaries to the user.
- Resume from pending clarification.
- Surface validation errors in user-friendly language.

Available backend capabilities:

- `start_memory_ingestion`
- source/process store
- ingestion services
- graph write-plan execution through backend services

Deferred decisions:

- When should ingestion execute writes automatically?
- When should the user confirm a write plan?
- How much detail should the user see after successful ingestion?
- How should partial ingestion failures be explained?

Locked integration direction:

- The complete ingestion workflow must be LLM-backed where appropriate:
  mention scan, graph-context-aware planning, focused extraction,
  contradiction-sensitive reasoning, and user-friendly clarification.
- Contradiction doubts should be inferred by the active agent/process from the
  provided source and graph context, not detected through brittle deterministic
  rules.
- If an ingestion/planning/resolution state sees ambiguity or conflict that
  requires judgment, it may invoke `contradiction_review` through its configured
  tooling/handoff path.

### Clarification Manager

Purpose:

Store pending questions and provide enough context for the runtime or agent to decide whether a later user message should resume the process.

Responsibilities:

- Store pending clarification context.
- Attach pending context to the next relevant runtime or agent call.
- Support classification of the next user message as clarification answer, new memory, question, correction, cancellation, or normal chat.
- Resume the pending process only when classification indicates that resumption is appropriate.
- Pause, cancel, or expire old pending states.
- Let the user cancel or skip when appropriate.
- Avoid turning chat into a rigid form flow.

Locked behavior:

- Clarification questions are normal assistant messages, not broad
  model-visible tools.
- Pending process state is contextual guidance, not deterministic routing.
- Optional lightweight classification may be used only when it helps decide
  whether to resume a pending process.
- Paused pending processes are distinct from cancelled pending processes.
- Proactive resurfacing of paused questions is deferred.

Deferred decisions:

- What is the default expiration duration?
- Can multiple paused pending clarifications exist at once?
- If a user ignores a clarification and sends a new memory, should the old one
  always pause, or can some cases cancel immediately?
- How should ambiguous clarification answers be handled?
- Which parts of message classification should be deterministic versus
  model-guided once real routing is enabled?

### Memory Query Process

Purpose:

Answer user questions using graph context and source evidence.

Responsibilities:

- Convert a question into retrieval intent.
- Retrieve graph context and evidence.
- Decide whether more context is needed.
- Generate a grounded answer.
- Include uncertainty when evidence is weak.
- Keep affective memory and original user wording available where relevant.

Available backend capabilities:

- `query_memory_context`
- graph context packages
- timeline and neighborhood views
- vector retrieval later
- answer generation through AI provider later

Deferred decisions:

- How much retrieval should happen before answer generation?
- When should semantic/vector retrieval be used?
- How should the answer cite or summarize evidence?
- How should the assistant answer when the graph has no memory?

### Memory Correction Process

Purpose:

Turn user corrections into safe graph changes or correction proposals.

Responsibilities:

- Identify correction target.
- Retrieve current and historical facts.
- Propose safe change.
- Ask confirmation when risky.
- Create change records through graph services.

Available backend capabilities:

- `propose_memory_correction`
- graph query services
- lifecycle transition services
- change records
- merge services later

Deferred decisions:

- Which corrections can be applied automatically?
- Which corrections require confirmation?
- How should corrections preserve the older memory rather than erasing it?
- How should "I was wrong" differ from "this changed over time"?

### Contradiction Judge

Purpose:

Review grounded contradiction doubts raised by memory-writing or query processes.

Responsibilities:

- Receive a contradiction doubt with evidence.
- Inspect additional graph context through read-only tools when allowed.
- Decide severity and recommended action.
- Recommend clarification, ignore, mark disputed, or create contradiction record.

Important boundary:

The judge does not mutate the graph directly.

Deferred decisions:

- What severity levels are useful?
- When is the judge invoked automatically?
- Which read-only tools can the judge use?
- When should the user be interrupted with a contradiction clarification?

### Profile And Personality Memory Process

Purpose:

Detect durable user traits, preferences, personality hints, and assistant-configuration memory.

Responsibilities:

- Separate stable traits from temporary moods.
- Prefer explicit user statements over inference.
- Mark sensitive traits as confirmation-required.
- Store evidence and lifecycle state.
- Make approved profile memory retrievable during prompt construction.

Deferred decisions:

- Which profile keys are allowed?
- What requires explicit confirmation?
- How should profile memory be edited or forgotten?
- How should personality-cloning experiments be isolated from normal product behavior?

### Memory Maintenance Process

Purpose:

Suggest or perform maintenance actions over time.

Potential responsibilities:

- Duplicate review.
- Weak metadata review.
- Stale contact update suggestions.
- Missing source/evidence review.
- Low-confidence extraction review.
- Merge/split suggestions.

Deferred decisions:

- Which maintenance tasks are proactive versus user-triggered?
- How much automation is acceptable for a personal project?
- How should suggestions avoid becoming annoying management flows?

## Process Specification Template

Every agent/process should eventually be specified with this template:

```text
Name:
Purpose:
Owner:
Trigger conditions:
Inputs:
Required context:
Produced context:
Context object type:
Context handoff policy:
History policy:
Tool trace policy:
Allowed tools:
Forbidden tools:
Tool/output contracts:
State transitions:
Clarification policy:
Confirmation policy:
Retry/fallback policy:
Privacy policy:
Model routing:
Evaluation examples:
Open decisions:
```

## Tooling Design Template

Every model-visible tool should eventually be specified with this template:

```text
Tool name:
Purpose:
Who can call it:
When to call it:
When not to call it:
Input schema:
Output schema:
Side effects:
Confirmation requirement:
Failure modes:
Verbose tool errors:
Examples:
```

## Context Object Design

Wave 1 introduced baseline typed context objects for state inputs and handoffs.
They are not the same as raw chat messages, raw tool traces, or database
records. They are deliberate packages assembled after each action finishes.

Purpose:

- Make every state input explicit and testable.
- Avoid leaking noisy internal tool traces into future prompts.
- Keep previous-step outputs available without passing whole implementation
  details.
- Support deterministic validation before a state or subprocess starts.
- Make prompt rendering stable because each prompt receives a known context
  object shape.

Implemented baseline object families:

- `ConversationContext`: usable conversation history, compacted older summary,
  current message, current time/timezone, and pending-process summary.
- `PendingProcessContext`: active or paused process refs, original question,
  unresolved targets, expiration, and compact process summary.
- `ChannelSessionMetadata`: backend-owned transport/session object; not passed
  to the LLM by default.
- `ChannelContextProjection`: minimal model-facing projection when channel
  details matter, such as modality or response rendering constraints.
- `SourceContext`: normalized source text/transcript, media refs, source timing,
  and source/evidence refs.
- `MentionScanContext`: shallow mentions, evidence spans, and rough hints for
  context retrieval.
- `GraphContextPackage`: compact graph context with aliases, candidate matches,
  relationship contexts, evidence summaries, and known ambiguities.
- `PlanningContext`: source context, conversation context, mention scan, graph
  context, current time/timezone, and pending clarification answer when
  resuming.
- `ExtractionTaskContext`: focused evidence span, selected schema, graph aliases,
  and local candidate refs needed by a single extractor.
- `CandidateGraphContext`: assembled candidates, local refs, source refs, and
  evidence refs.
- `ResolutionContext`: candidate graph, graph context, registries, resolver
  constraints, and pending-answer context.
- `ToolResultContext`: compact output summary returned from a tool/subprocess to
  its caller, including result status, important refs, unresolved questions,
  errors, and recommended next action.
- `AnswerContext`: LLM-ready context package for grounded answer generation.

Future waves may extend these contracts, but they should not replace the core
handoff rule: every action boundary produces an explicit context object for the
next state.

Handoff rule:

Every action boundary should produce one explicit context object for the next
state. Internal traces can be persisted for audit/debugging, but parent states
should receive compact `ToolResultContext` objects unless deeper details are
explicitly requested.

Example:

```text
AS: memory_ingestion_planning
  receives PlanningContext
  calls LP: focused_extraction

LP: focused_extraction
  receives ExtractionTaskContext
  appends internal provider/tool diagnostics locally
  returns FocusedExtractionResult

BP: candidate_assembly
  receives focused extraction results
  returns CandidateGraphContext

AS parent history
  receives one compact ToolResultContext summarizing the subprocess result,
  not every internal provider call.
```

## Wave 0: Design Baseline

Status: Complete.

### Summary

Lock the agent/process catalog, process template, top-level action surface, and
deferred decisions.

### Outputs

- Canonical roadmap and baseline implementation plan.
- Initial process catalog.
- Initial tool design template.
- Initial context object catalog and handoff rule.
- Canonical state architecture maintained in [Agentic orchestration architecture](../architecture/agentic-orchestration.md).
- Implementation waves derived from the architecture design.
- Agreement that full agent behavior is separate from chat adapter implementation.

### Completion Criteria

- Future implementation work has a clear place for agent design.
- `03` can proceed without hiding behavioral complexity.
- The team understands which behavior is not yet designed.

## Wave 1: Router And Clarification Protocols

Status: Complete.

### Summary

Implement the first foundation slice for agentic runtime behavior. This wave is
mostly contracts and scaffolding, not full autonomous behavior.

Focus:

- Typed context objects.
- Neutral conversation message protocol.
- Prompt registry and prompt template loading.
- Agentic state configuration models.
- Tool-call/message protocol contracts.
- Conversation router.
- Pending clarification handling.
- Status/cancel behavior.
- Start-ingestion behavior from text and transcript inputs.

Implemented outputs:

- Deterministic router protocol.
- Pending process review protocol skeleton.
- `conversation_entry` state configuration.
- `pending_process_review` state configuration.
- Router input context shape.
- `ConversationContext`.
- `PendingProcessContext`.
- `ChannelSessionMetadata`.
- `ChannelContextProjection`.
- `ToolResultContext` for router/pending-process actions.
- Neutral message models:
  - user message
  - assistant message
  - assistant tool call
  - tool output
  - compacted summary
- Prompt registry and initial templates:
  - `conversation_entry`
  - `pending_process_review`
  - optional `clarification_classifier`
- Agentic state configuration model.
- Router tool-call/message protocol.
- Pending process context shape.
- Optional lightweight pending-message intent classification.
- Minimal clarification state transitions.
- Tests/evaluation examples for:
  - new memory
  - direct question
  - clarification answer
  - correction attempt
  - user changes topic while clarification is pending
  - user sends a different memory while clarification is pending
  - user cancels or skips a pending clarification

Verification:

- `tests/test_agentic_foundation.py`
- Full suite: `117 passed, 3 skipped`

Real OpenAI/Azure tool-call routing can be wired after the contracts, prompts,
and deterministic fallback router are stable.

Out of scope for Wave 1:

- Real autonomous routing in production.
- Complex prompt tuning.
- Proactive resurfacing of paused pending processes.
- Full agent-to-chat runtime wiring beyond clear interfaces and tests.

## Wave 2: Query And Answer Foundation

Status: Complete.

### Summary

Implement the agentic query and answer foundation on top of existing graph
query/context package services. This wave should make memory questions flow
through explicit context objects and prompt contracts without yet enabling a
fully autonomous assistant.

Focus:

- `memory_query` state configuration.
- Query retrieval planning contract.
- Query context retrieval handoff.
- `AnswerContext`.
- Answer-generation prompt template.
- Query intent interpretation.
- Retrieval plan.
- Evidence package construction.
- Grounded answer generation.
- Uncertainty handling.
- No-memory answer behavior.

Implemented outputs:

- Query process protocol.
- `memory_query` state configuration.
- Query retrieval planning context object.
- Query retrieval result context object.
- `AnswerContext`.
- Query tool result context object.
- Prompt templates:
  - `memory_query`
  - `query_retrieval_planning`
  - `answer_generation`
- Deterministic query fallback path using existing graph query/context helpers
  where available.
- Answer-generation prompt contract.
- Evidence presentation rules.
- Tests/evaluation examples for:
  - person memories
  - timeline questions
  - place questions
  - affective relationship questions
  - missing memories

Verification:

- `tests/test_agentic_query_foundation.py`
- Full suite: `122 passed, 3 skipped`

Out of scope for Wave 2:

- Semantic text-to-node retrieval beyond existing graph query helpers.
- Real autonomous multi-tool query loops.
- Public product-grade citation UI.
- Frontend graph/dashboard behavior.

## Wave 3: Correction, Judge, Profile, And Maintenance Foundation

Status: Complete.

### Summary

Implement the contracts and prompt scaffolding for higher-risk and later-stage
agentic processes. Mutation still remains backend-owned and confirmation-aware.

Focus:

- Correction process.
- Contradiction judge.
- Profile/personality memory process.
- Maintenance process.

Implemented outputs:

- Correction protocol.
- Correction context objects and confirmation handoff context.
- `correction_intake` state configuration.
- Correction proposal prompt template.
- Judge invocation rules.
- Judge review context object and judge result context object.
- `contradiction_review` state configuration.
- Contradiction judge prompt template.
- Judge output schema.
- Profile memory extraction policy.
- Profile extraction context object.
- Profile memory prompt template.
- Maintenance suggestion policy.
- Maintenance review context object.
- Maintenance review prompt template.
- Confirmation rules for risky changes.

Implemented files:

- `src/my_digital_brain/agentic/enums.py`
  - contradiction decisions, severity, and graph actions
  - correction actions
  - confirmation risk levels
  - profile memory category, stability, and visibility
  - maintenance suggestion types
- `src/my_digital_brain/agentic/contexts.py`
  - `CorrectionIntakeContext`
  - `CorrectionProposalContext`
  - `ConfirmationHandoffContext`
  - `ContradictionReviewContext`
  - `ContradictionJudgeResultContext`
  - `ProfileExtractionContext`
  - `ProfileMemoryCandidateContext`
  - `ProfileExtractionResultContext`
  - `MaintenanceReviewContext`
  - `MaintenanceSuggestionContext`
  - `MaintenanceReviewResultContext`
- `src/my_digital_brain/agentic/state.py`
  - `correction_intake` state configuration
  - `contradiction_review` state configuration
- Prompt templates:
  - `correction_intake/v1.system.md`
  - `correction_proposal/v1.system.md`
  - `contradiction_review/v1.system.md`
  - `profile_memory_extraction/v1.system.md`
  - `maintenance_review/v1.system.md`
- `tests/test_agentic_risk_foundation.py`

Verification:

- `python -B -m pytest tests/test_agentic_risk_foundation.py`
- Full suite: `128 passed, 3 skipped`

Out of scope for Wave 3:

- Direct graph mutation by models.
- Fully autonomous maintenance prompts.
- Personality-cloning behavior in normal MVP flows.
- Public multi-user policy.

## Focused MVP Integration Slice

Status: Complete.

### Summary

Implement only the missing features needed to make the current agentic product
flow usable without pulling in future hardening work.

Implemented outputs:

- Opt-in `agentic` mode in `ChatRuntime`; deterministic mode remains the
  default.
- Explicit `/status` and `/cancel` deterministic shortcuts are preserved as
  developer/debug control paths, not normal product UX.
- Incoming agentic chat messages now flow through message persistence,
  `ConversationContext` construction, `AgenticToolExecutionContext`
  construction, `AgenticRuntime.run(...)`, response rendering, assistant
  persistence, and pending-process persistence when needed.
- `AgenticHistoryService` centralizes state-aware history construction,
  model-facing payload projection, backend-only metadata exclusion, and compact
  nested tool-output summaries.
- Final assistant-message ownership is enforced for normal completion paths:
  specialist outputs are compacted back to the conversational owner, and the
  owner state writes the user-visible final message with tools disabled.
- Contradiction review final output is structurally enforced through
  `ContradictionJudgeResultContext`; runtime behavior is driven by explicit
  intents rather than free-form assistant text.
- Active pending process context starts the runtime from
  `pending_process_review` instead of forcing the next message through a
  deterministic clarification route.
- `AgenticIngestionPlanner` runs the `memory_ingestion_planning` state through
  the existing provider tool-call loop for support tools, then requires a
  structured `ExtractionPlan` final output.
- The planner toolbox includes:
  - `request_graph_context_expansion`
  - `request_contradiction_review`
- After the structured `ExtractionPlan` is returned and validated, backend code
  deterministically routes the next ingestion step from the plan fields.
- Full ingestion remains owned by `IngestionService`: mention scan, graph
  context retrieval, planning, focused extraction, assembly, validation,
  resolution, write-plan creation, optional graph execution, clarification, and
  summary.
- Contradiction review is agent-invoked through tool handoff. No deterministic
  contradiction-detection rules were added.
- Contradiction review returns a structured result with intents:
  `needs_context`, `needs_clarification`, `emit_verdict`, and `fail_safe`.
  Clarification rendering comes from that structured result.
- `AgenticRunResult` is rendered into `ChatResponse` without exposing raw tool
  traces, UUID-heavy graph payloads, or backend internals.

Verification:

- `tests/test_chat_runtime.py`
- `tests/test_agentic_runtime.py`
- `tests/test_agentic_tool_bindings.py`
- `tests/test_ingestion_ai_planning.py`

Deferred by design:

- Real OpenAI/Azure smoke tests.
- LangSmith/remote tracing.
- Prompt tuning and broad eval suites.
- Post-UAT hardening.

## Out Of Scope For Now

- Implementing every agent.
- Building a fully autonomous assistant.
- Proactive maintenance prompts.
- Personality-cloning behavior in normal MVP flows.
- Public product multi-user policy.

## Guardrails

- Agents never directly write to persistence.
- Model-visible tools are narrow and explicit.
- Backend services own validation and mutation.
- Clarifications should be meaningful, not mechanical.
- User-facing language should remain simple and conversational.
- Tool loops need deterministic limits.
- Every persistent memory change needs provenance.
- Sensitive or identity-changing actions need confirmation.
- Context must be scoped and low-noise.
- Raw metadata and raw UUIDs should not be dumped into prompts.
- Final assistant-message rendering is owned by the upper conversational layer,
  with the exception of deeper-state clarification questions that need to be
  shown to the user before the process can continue.
