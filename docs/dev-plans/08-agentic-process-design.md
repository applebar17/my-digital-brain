# Agentic Process Design And Definition

## Goal

Define the behavioral protocols, toolboxes, context packages, and guardrails for the AI-driven processes that operate on top of the backend services.

This plan is mostly a design placeholder for now. It exists because the product cannot be reduced to "chat input goes to ingestion." The core product behavior depends on how agents reason, choose tools, ask clarifications, interpret graph context, recover from failures, and coordinate subprocesses.

## Expected Output

This plan should produce agent/process specifications before heavy implementation.

Expected artifacts:

- Agent responsibility definitions.
- Behavioral protocols.
- Allowed and forbidden tools per agent/process.
- Input context requirements.
- Structured output contracts.
- State transition diagrams or tables.
- Clarification rules.
- Confirmation rules.
- Error and retry policies.
- Model routing policy by task difficulty.
- Privacy and provider-boundary rules.
- Evaluation examples for each process.

The final output is not just code. The most important output is a clear behavioral contract that future implementation can follow.

## Architecture Position

```text
Chat consumers
Telegram, web chat, future mobile
        |
        v
Conversation runtime
normalization, sessions, pending state
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

This plan defines how agents and subprocesses behave when using those pieces.

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
- Internal UUIDs should be replaced with scoped aliases in model-facing contexts.
- Tool errors must be verbose enough to guide model recovery.
- Clarifications should be user-friendly and sparse enough to avoid fatigue.
- Risky graph mutations require confirmation or conservative fallback.

## Agent And Process Catalog

### Conversation Router

Purpose:

Decide whether a user message should be answered directly or routed into a process.

Possible actions:

- default answer path
- start memory ingestion
- answer pending clarification
- query memory context
- propose memory correction
- report status or failure

Design questions:

- Should routing be deterministic first, LLM-based, or hybrid?
- What context does routing need beyond the current message?
- When should a message be treated as a clarification answer instead of a new memory?
- Which commands remain deterministic shortcuts?

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

Open design questions:

- When should ingestion execute writes automatically?
- When should the user confirm a write plan?
- How much detail should the user see after successful ingestion?
- How should partial ingestion failures be explained?

### Clarification Manager

Purpose:

Handle pending questions and route user replies to the right process.

Responsibilities:

- Store pending clarification context.
- Decide whether the next user message answers the question.
- Resume the pending process.
- Expire old pending states.
- Let the user cancel or skip when appropriate.

Open design questions:

- What is the default expiration duration?
- Can multiple pending clarifications exist at once?
- If a user ignores a clarification and sends a new memory, should the old one stay pending?
- How should ambiguous clarification answers be handled?

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

Open design questions:

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

Open design questions:

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

Open design questions:

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

Open design questions:

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

Open design questions:

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
Allowed tools:
Forbidden tools:
Structured outputs:
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

## Wave 0: Design Baseline

### Summary

Lock the agent/process catalog, process template, top-level action surface, and open questions.

### Outputs

- This placeholder plan.
- Initial process catalog.
- Initial tool design template.
- Agreement that full agent behavior is separate from chat adapter implementation.

### Completion Criteria

- Future implementation work has a clear place for agent design.
- `03` can proceed without hiding behavioral complexity.
- The team understands which behavior is not yet designed.

## Wave 1: Router And Clarification Protocols

### Summary

Design the first behavioral protocols needed for a usable chat loop.

Focus:

- Conversation router.
- Pending clarification handling.
- Status/cancel behavior.
- Start-ingestion behavior from text and transcript inputs.

Expected design outputs:

- Router protocol.
- Clarification manager protocol.
- Router input context shape.
- Router output schema.
- Clarification state transitions.
- Evaluation examples for:
  - new memory
  - direct question
  - clarification answer
  - correction attempt
  - user changes topic while clarification is pending

Implementation should wait until these protocols are stable enough.

## Wave 2: Query And Answer Protocols

### Summary

Design how the assistant answers memory questions from graph context.

Focus:

- Query intent interpretation.
- Retrieval plan.
- Evidence package construction.
- Grounded answer generation.
- Uncertainty handling.
- No-memory answer behavior.

Expected design outputs:

- Query process protocol.
- Query context package shape.
- Answer-generation prompt contract.
- Evidence presentation rules.
- Evaluation examples for:
  - person memories
  - timeline questions
  - place questions
  - affective relationship questions
  - missing memories

## Wave 3: Correction, Judge, Profile, And Maintenance Protocols

### Summary

Design the higher-risk and later-stage agentic processes.

Focus:

- Correction process.
- Contradiction judge.
- Profile/personality memory process.
- Maintenance process.

Expected design outputs:

- Correction protocol.
- Judge invocation rules.
- Judge output schema.
- Profile memory extraction policy.
- Maintenance suggestion policy.
- Confirmation rules for risky changes.

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
