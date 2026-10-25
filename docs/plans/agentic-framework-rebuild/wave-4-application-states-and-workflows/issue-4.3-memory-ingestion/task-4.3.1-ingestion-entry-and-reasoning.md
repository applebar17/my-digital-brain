# Task 4.3.1 — define ingestion request and reasoning context

**Status: Not started**

## User story

As the conversation-entry state or API, I want to start ingestion with the
user input and correct owner/conversation context, so the ingestion states can
interpret what the user meant without stale or hard-coded identity data.

## What and why

Use the agreed state-slice sequence: first confirm this state's functional
purpose, caller, inputs, output, and whether it is in fact an agentic state.
Then define only the DTOs/artifacts, prompt/context/history, deterministic
functions, and tools needed for that agreed behavior. Include model-facing
owner projection and relevant history if required; reasoning/planning remains
optional rather than assumed.

## Where

- `src/product/application/states/ingestion/` request and reasoning state.
- Owner and reference rendering per the canonical context specification.

## Functional communication boundary

Candidate input: user content, owner identity, and relevant
conversation/channel context. Candidate result: the
functional outcome this state's caller needs. The exact result fields are
defined only after the state purpose is agreed. The owner shown to the model is
a functional identity projection, not the backend owner UUID.

## Dependencies and acceptance

- Follows the approved state inventory in Task 4.0.1 and uses the generic
  framework from Wave 2.
- Add a Wave 3 service/tool dependency only when the agreed state behavior
  requires it.
- Owner context is derived per invocation, never hard-coded or stale.
- Reasoning receives relevant history and input context, not only an isolated
  goal string.
- No proposed action or reasoning artifact is mistaken for a completed write.
