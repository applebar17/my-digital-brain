# Task 4.3.1 — define ingestion request and reasoning context

**Status: Not started**

## User story

As the conversation-entry state or API, I want to start ingestion with the
source and correct owner/conversation context, so the ingestion states can
interpret what the user meant without stale or hard-coded identity data.

## What and why

Define the high-level ingestion input/output DTOs and the initial reasoning
state context. Include model-facing owner projection and relevant history;
reasoning/planning remains optional according to the state specification.

## Where

- `src/product/application/states/ingestion/` request and reasoning state.
- Owner and reference rendering per the canonical context specification.

## Functional communication DTOs

Input: source/user content, owner identity, conversation/channel context, and
optional media/evidence references. Output from reasoning: salient entities,
relationships, context gaps, evidence, and whether a clarification is useful.
The owner shown to the model is a functional identity projection, not the
backend owner UUID.

## Dependencies and acceptance

- Depends on Tasks 2.3.2 and 3.1.1.
- Owner context is derived per invocation, never hard-coded or stale.
- Reasoning receives relevant history and source context, not only an isolated
  goal string.
- No proposed action or reasoning artifact is mistaken for a completed write.
