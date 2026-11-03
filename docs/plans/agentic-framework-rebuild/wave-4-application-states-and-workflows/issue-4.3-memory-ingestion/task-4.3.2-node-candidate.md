# Task 4.3.2 — define the node-candidate state

**Status: Complete**

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
resolution slice. The state does not receive copied source messages or
message-source identifiers. The exact candidate variants are agreed during
this task; they are not represented by a free-form property bag.

The fixed response covers `Person`, `Event`, `Place`, `Organization`, `Object`,
`Animal`, `SocialCircle`, and `KnowledgeItem`. Knowledge-item kinds are `topic`,
`concept`, `idea`, `insight`, `reminder`, `quote`, `reference`, and `other`. The
workflow derives the present types from returned candidates and can use that
set to compact later state/tool configuration. There is no separate candidate
census call and no model-generated duplicate type inventory.

## Dependencies and acceptance

- Depends on Tasks 4.3.0a, 4.3.0b, and 4.3.1.
- The prompt and Pydantic field descriptions have one coherent semantic
  contract.
- No candidate is reported as an existing identity or completed graph write.
- The workflow exposes the typed candidate result as the declared input for the
  subsequent deterministic lookup slice.
- Inspector output shows the state input/output, prompt, lack of extra stages,
  and effective empty toolbox.
- Graph topology, persistence interfaces, and write tools for `KnowledgeItem`
  and migration of the existing `Topic` representation are deferred to the
  indexed topology-alignment task and are
  not implemented in this read-only state.

