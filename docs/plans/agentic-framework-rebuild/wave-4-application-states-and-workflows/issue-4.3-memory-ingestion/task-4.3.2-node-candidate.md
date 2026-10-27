# Task 4.3.2 — define the node-candidate state

**Status: Not started**

## User story

As the ingestion workflow, I want a typed inventory of objects mentioned in
the inherited conversation, so identity lookup and later writes operate on
explicit candidates rather than reinterpreting unstructured text.

## What and why

Define `NodeCandidateState` as one structured main LLM call. Its implementation
slice consists primarily of its input/output DTOs, versioned prompt, toolbox
configuration, and workflow handoff. It receives inherited conversational
history, the completed ingestion-reasoning result, and relevant known
references. It has no separate framework reasoning/planning stage.

The state identifies typed candidates but does not query the graph, decide
identity, allocate backend IDs, or write anything. No toolbox is configured
unless a concrete reviewed requirement proves that candidate generation needs
one. Candidate reference registration and deterministic identity lookup happen
after this state completes.

## Where

- `src/product/application/states/ingestion/node_candidate/` models and state.
- Versioned node-candidate prompt.
- Memory-ingestion workflow step and inspector configuration.

## Functional communication boundary

Input: inherited history, `IngestionReasoningResultDTO`, model-facing owner and
known-reference context where relevant. Output: explicit typed object
candidates with only the fields required by the later identity-lookup and
resolution slice. The exact candidate variants are agreed during this task;
they are not represented by a free-form property bag.

## Dependencies and acceptance

- Depends on Tasks 4.3.0a, 4.3.0b, and 4.3.1.
- The prompt and Pydantic field descriptions have one coherent semantic
  contract.
- No candidate is reported as an existing identity or completed graph write.
- The workflow passes the typed candidate result to deterministic lookup.
- Inspector output shows the state input/output, prompt, lack of extra stages,
  and effective empty toolbox.

