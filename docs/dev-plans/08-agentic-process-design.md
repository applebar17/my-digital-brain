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
- `src/my_digital_brain/prompts/`
  - file-backed prompt registry
  - initial templates for `conversation_entry`, `pending_process_review`, and
    optional `clarification_classifier`
- `tests/test_agentic_foundation.py`
  - neutral message validation
  - context payload safety
  - default state toolbox checks
  - prompt registry loading/rendering
  - deterministic router behavior

Implemented but intentionally not wired yet:

- Real OpenAI/Azure tool-call routing.
- Agentic runtime integration into `ChatRuntime`.
- Model-backed intent classification.
- Query/answer agentic protocols.
- Correction/judge/profile/maintenance protocols.

This is intentional. The current code provides stable contracts and fake/test
provider-compatible behavior before production model behavior is connected.

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
- `get_conversation_status`
- `cancel_pending_process`

Locked behavior:

- When no active pending process exists, `conversation_entry` is the default
  entry state.
- When an active pending process exists, `pending_process_review` is the
  preferred entry state.
- Orchestrator-like states return either an assistant message or a model-visible
  tool call.
- The tool call is the structured routing decision.
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

Status: Pending.

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

Expected implementation outputs:

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
- Evaluation examples for:
  - person memories
  - timeline questions
  - place questions
  - affective relationship questions
  - missing memories

Out of scope for Wave 2:

- Semantic text-to-node retrieval beyond existing graph query helpers.
- Real autonomous multi-tool query loops.
- Public product-grade citation UI.
- Frontend graph/dashboard behavior.

## Wave 3: Correction, Judge, Profile, And Maintenance Foundation

Status: Pending.

### Summary

Implement the contracts and prompt scaffolding for higher-risk and later-stage
agentic processes. Mutation still remains backend-owned and confirmation-aware.

Focus:

- Correction process.
- Contradiction judge.
- Profile/personality memory process.
- Maintenance process.

Expected implementation outputs:

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

Out of scope for Wave 3:

- Direct graph mutation by models.
- Fully autonomous maintenance prompts.
- Personality-cloning behavior in normal MVP flows.
- Public multi-user policy.

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
