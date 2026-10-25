# Task 4.0.1 — census memory-ingestion states and handoffs

**Status: Complete**

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

## Confirmed decisions

- The state boundaries and deterministic execution order are accepted as shown
  in the reusable workflow map. A later state may be split or combined only for
  a concrete functional reason discovered during its vertical slice.
- No ingestion state currently adds a separate framework reasoning or planning
  call. Each documented main LLM call performs its stated responsibility.
- Node resolution, memory/context writing, and relationship writing may invoke
  `ClarificationAgentState` as an agentic tool. Its typed result returns as the
  matched tool output to the requesting state, which resumes before the
  workflow advances.
- `ConversationEntryState` is the agentic chat state. It invokes the bound
  `MemoryIngestionWorkflow.ingest_memory` method through a tool and resumes with
  the matched workflow result to generate the final chat response.
- At framework level, tools may bind either an agentic state or a workflow. The
  parent continuation contract is the same; only the internal handler differs.
- The MVP carries normalized input text or a transcript as transient workflow
  context. It does not require a persisted source record or original-message ID.
- Linked objects are written only after their required model-facing references
  have been resolved by earlier handoffs.

## Where

- The sequence and state inventory in the
  [memory-ingestion issue](README.md).
- Existing flow and AI-engineering state documents referenced by that issue.

## Functional communication overview

At this level, record only the meaning of each handoff (for example, normalized
input, resolved local references, or a completed write outcome). Concrete
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
