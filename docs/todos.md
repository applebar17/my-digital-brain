# Project TODOs

This file tracks deferred work that is intentionally not part of the current
implementation slice. It should hold product-level follow-ups, not detailed
wave plans.

## Agentic Runtime And Chat Integration

- Wire `AgenticRuntime` into `ChatRuntime` as an opt-in mode.
- Build `ConversationContext` from persisted chat history, compacted summaries,
  current time/timezone, pending process refs, and channel metadata.
- Build `AgenticToolExecutionContext` from backend services, graph service,
  ingestion service, chat store, session ids, owner ids, and pending context.
- Keep deterministic chat behavior available until agentic behavior passes UAT.

## Full LLM Ingestion Workflow

- Implement the complete LLM-backed ingestion path:
  - source/transcript normalization
  - mention scan
  - compact graph context retrieval
  - `memory_ingestion_planning`
  - simple or focused extraction
  - candidate assembly
  - validation and resolution
  - write-plan creation
  - graph execution or clarification
  - ingestion summary
- Contradiction doubts should be inferred by the relevant agentic state from
  context, not deterministically detected by brittle hard-coded rules.
- Let ingestion/planning/resolution agents invoke `contradiction_review` through
  configured tooling when they see ambiguous or conflicting memory context.

## Assistant Message Rendering

- Conversation entry remains the owner of the final user-visible assistant
  message after a full process completes.
- Deeper states may render user-visible clarification questions when the
  process cannot safely continue without user input.
- Tool traces, graph payloads, and raw backend diagnostics must stay internal
  unless explicitly transformed into a user-facing summary.
- Define rendering rules for:
  - normal direct answers
  - ingestion summaries
  - memory query answers
  - correction proposals
  - confirmation questions
  - clarification questions from deeper states
  - failed or partially completed processes

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
