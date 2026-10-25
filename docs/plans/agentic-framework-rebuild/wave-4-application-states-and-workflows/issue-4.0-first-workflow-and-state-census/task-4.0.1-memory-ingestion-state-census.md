# Task 4.0.1 — census memory-ingestion states and handoffs

**Status: Not started**

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
