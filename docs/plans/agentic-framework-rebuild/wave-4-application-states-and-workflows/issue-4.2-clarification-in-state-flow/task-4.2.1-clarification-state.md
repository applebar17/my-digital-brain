# Task 4.2.1 — define clarification request/result and implement the child state

**Status: Completed**

## User story

As an invoking state with a material context gap, I want a clarification agent
to analyze the goal and relevant context and ask one natural, answerable
question, so I can use the user's answer to continue my work.

## What and why

Define the functional request/result DTOs and implement the clarification state
with its configured question tool. The question should explain the ambiguity in
human terms; it must not expose internal refs or act as a final answer to the
parent.

## Where

- `src/product/application/states/clarification/` and its versioned prompt.
- `src/product/application/interactions/` question packet and deadline service.
- `src/product/application/tools/user_interaction/` tool registration.

## Functional communication DTOs

Request: a descriptive LLM-generated `clarification_ref`, goal,
context/evidence, and the specific uncertainty to resolve.

Interaction: a human-readable question configured as one of `free_response`,
`confirmation`, `single_choice`, or `multiple_choice`, with options only where
useful. Confirmation and choice modes carry `allow_other`, enabled by default,
so the client can deterministically expose an Other/correction text input. This
flag is set by the backend and is not part of the LLM tool arguments. The
interaction model stays generic: it does not define separate date, number,
entity, location, file, or other domain-specific question types. The LLM
phrases the question and interprets the natural-language answer.

Result to caller: the same `clarification_ref`, the user's answer or timeout
outcome, and the resolved point or remaining uncertainty in functional
language. The child state, rather than the deterministic UI tool, interprets
the raw interaction result.

## Dependencies and acceptance

- Depends on Issues 2.3, 3.1.3, and 3.2.2.
- The child does not return its question as a completed answer to the parent.
- The parent receives the resolved answer only after the user responds.
- Internal clarification identity is not confused with provider call IDs.
- The new implementation does not migrate the previous broad response-mode
  taxonomy or its per-mode validation rules.
