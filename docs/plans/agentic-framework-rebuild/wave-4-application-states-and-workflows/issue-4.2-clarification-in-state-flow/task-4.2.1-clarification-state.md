# Task 4.2.1 — define clarification request/result and implement the child state

**Status: Not started**

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

- `src/product/application/states/clarification.py` and its prompt.
- `product.application.tools` question/interaction registration.

## Functional communication DTOs

Request: goal, context/evidence, and the specific uncertainty to resolve.
Interaction: human-readable question and supported answer mode/options.
Result to caller: clarification reference plus the user's answer and the
resolved point in functional language.

## Dependencies and acceptance

- Depends on Issues 2.3, 3.1.3, and 3.2.2.
- The child does not return its question as a completed answer to the parent.
- The parent receives the resolved answer only after the user responds.
- Internal clarification identity is not confused with provider call IDs.
