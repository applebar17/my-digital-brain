# Task 4.2.2 — connect question and answer to the invoking state

**Status: Completed**

## User story

As an invoking state, I want a clarification child call to pause visibly and
then return its resolved output through the original tool handoff, so my
reasoning/planning can continue with the answer in context.

## What and why

Wire the clarification state's question tool to the product interaction and
continuation boundary. On answer or timeout, resolve the child tool call once;
on child completion, return one typed result to the parent call and let the
parent LLM continue normally. Durable SQL/API composition remains Task 5.1.1.

## Where

- `src/product/application/tools/clarification/` agent-as-tool handoff.
- `src/product/application/interactions/` typed answer, timeout, and in-process
  continuation boundary.
- `src/product/agentic/history/` parent/child run linkage.
- Task 5.1.1 for durable API/frontend adaptation.

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
- Functional tests prove both timely-answer and timeout paths resume the child
  before producing the original parent tool output.
