# Task 4.2.2 — connect question and answer to the invoking state

**Status: Not started**

## User story

As an invoking state, I want a clarification child call to pause visibly and
then return its resolved output through the original tool handoff, so my
reasoning/planning can continue with the answer in context.

## What and why

Wire the clarification state's question tool to the application's existing
interaction and continuation adapter. On answer or timeout, resolve the child
tool call once; on child completion, return one typed result to the parent call
and let the parent LLM continue normally.

## Where

- Clarification state/tool registration and application workflow composition.
- Existing API/frontend interaction contract, adapted only as needed.

## Functional communication DTOs

The UI receives the question packet and backend-generated `interaction_ref`.
The backend resolves the interaction from a timely user response or its
configured timeout, then resumes the clarification run. A retry of the same
logical doubt retains its LLM-generated `clarification_ref` but creates a new
`interaction_ref`.

Child completion returns the original `clarification_ref`, interpreted answer
or timeout outcome, and resolved uncertainty to the parent. The provider client
alone owns the provider call ID and pairs that child result to the original
tool call. These three references must not substitute for one another.

## Dependencies and acceptance

- Depends on Tasks 2.2.2, 3.1.3, and 4.2.1.
- One user answer resumes the correct child run and parent invocation.
- Parent receives one output and produces its own next response/tool call.
- The backend-owned deadline is configurable at composition; timeout becomes a
  normal typed result and does not terminate the child or parent pipeline.
- No standalone clarification runtime, second transcript manager, or duplicate
  frontend workflow is introduced.
