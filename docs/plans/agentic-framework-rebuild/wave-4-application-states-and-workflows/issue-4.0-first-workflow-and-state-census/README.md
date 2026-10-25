# Issue 4.0 — select the first workflow and census its states

**Status: Not started**

## Purpose

Start application delivery from a defined functional workflow rather than a
prebuilt inventory of graph services or LLM tools. The first workflow is
memory ingestion, using the existing deterministic ingestion sequence as a
working reference.

The reusable [workflow architecture map](../../../../architecture/memory-ingestion-workflow-map.md)
owns the visual sequence and step descriptions. The preceding
[local inspector issue](../issue-4-prep-workflow-inspector/README.md) prepares
the developer view used while validating the states.

## Tasks

- [Task 4.0.1 — census memory-ingestion states and handoffs](task-4.0.1-memory-ingestion-state-census.md)

## Expected result

An agreed ordered map that distinguishes agentic states from deterministic
steps, shows each handoff at a functional level, and identifies unresolved
decisions. The census does not freeze DTO schemas or tool lists. Those are
defined with each state, as its need becomes clear.

## Dependencies and boundaries

- Uses the generic agentic state, history, tool, and toolbox framework already
  established in Wave 2.
- Uses the current [ingestion flow](../../../../flows/ingestion.md) and
  [ingestion state documents](../../../../ai-engineering/application-states/ingestion/README.md)
  as review material, not as an automatic commitment to every existing step or
  contract.
- Graph, retrieval, owner, and interaction capabilities from Wave 3 are pulled
  in only when an agreed state requires them.
