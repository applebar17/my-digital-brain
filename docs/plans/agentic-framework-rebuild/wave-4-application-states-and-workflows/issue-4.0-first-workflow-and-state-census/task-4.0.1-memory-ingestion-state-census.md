# Task 4.0.1 — census memory-ingestion states and handoffs

**Status: In progress — architecture map drafted for review**

## User story

As the product owner, I want the memory-ingestion workflow broken down into its
required agentic states and deterministic steps before defining their detailed
contracts, so each later state slice is purposeful and ordered.

## What and why

Review the existing target ingestion sequence and identify, in order:

- the functional responsibility of each step;
- whether it is an LLM-backed agentic state or deterministic application work;
- the functional information entering and leaving the step;
- state-to-state or state-to-service handoffs and their dependencies;
- unresolved product decisions or context gaps.

This task is a census and agreement step, not implementation. Do not define
final Pydantic schemas, provider tool JSON, or graph service methods here.

## Reusable workflow reference

The [memory-ingestion workflow map](../../../../architecture/memory-ingestion-workflow-map.md)
is the reusable source for the diagram, agentic-versus-deterministic
classification, functional inputs and outputs, and each AI state's current
reasoning/planning call profile. Keep that map in architecture documentation;
this task records the review and decisions needed before state implementation.

## Decisions to confirm in this census

- Confirm the state boundaries and the execution order against the functional
  ingestion requirements; combine or split steps only for a concrete reason.
- Confirm which state, if any, needs a separate configured reasoning or planning
  call. The framework's capability alone does not enable such a call.
- Confirm which states can invoke `ClarificationAgentState` as an agentic tool,
  and how its typed result returns to the requesting state after the child uses
  its deterministic UI interaction tool.
- Confirm the meaning of each state-to-state handoff and the references required
  before memory, context, or relationship writes.
- Record any unresolved decision here; update the reusable workflow map once a
  decision changes the architecture.

## Where

- The sequence and state inventory in the
  [memory-ingestion issue](README.md).
- Existing flow and AI-engineering state documents referenced by that issue.

## Functional communication overview

At this level, record only the meaning of each handoff (for example, source
evidence, resolved local references, or a completed write outcome). Concrete
input/output DTOs and internal artifacts are defined during the corresponding
state task.

## Dependencies and acceptance

- Uses Wave 2's generic framework contracts; no new framework mechanism is
  introduced.
- The sequence distinguishes model decisions from deterministic lookup,
  persistence, and orchestration.
- Every agentic state has an identified caller and a functional result consumed
  by that caller or the next workflow step.
- Ordering dependencies are explicit, especially that linked objects use
  already-resolved references.
- The state inventory and execution order are reviewed before Task 4.3.1 begins.
