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
- Add richer resume behavior for paused or unresolved pending processes.
- Improve user-facing summaries after write-plan execution based on real UAT
  feedback.
- Add more evaluation examples for contradiction clarification wording.

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
