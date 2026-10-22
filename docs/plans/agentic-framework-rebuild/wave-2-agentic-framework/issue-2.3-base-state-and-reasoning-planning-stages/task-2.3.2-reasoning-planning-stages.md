# Task 2.3.2 — configure reasoning and planning stages

**Status: In review**

## User story

As a concrete state, I want to opt into structured reasoning and/or planning
with the relevant conversation context, so these stages improve that state's
main call without forcing every state through extra LLM calls.

## What and why

Implement only the configured reasoning/planning stages specified by the runtime
docs. Reasoning is independent; planning may consume the reasoning artifact.
Toolboxes are optional configuration, and default stage calls are
one-shot without tools. No hidden-reasoning output or mandatory multi-stage
pipeline is introduced.

## Where

- `src/product/agentic/` stage configuration and typed artifacts.
- Concrete state opts in from `product.application.states` when its functional
  spec requires it.

## Functional communication DTOs

Each stage receives the selected history/context and request. Reasoning returns
a typed `ReasoningArtifact`; planning receives that artifact when available and
returns a typed `PlanArtifact` for the owning state to use. Artifacts stay
internal unless the state contract explicitly returns them.

## Dependencies and acceptance

- Depends on Task 2.3.1 and the accepted reasoning/planning stage specification.
- A disabled stage adds no calls or output fields.
- Planning consumes reasoning only when configured and available.
- The main call receives artifacts as explicit context, not as forged assistant
  transcript turns.
- A stage pause resumes the same configured stage through an internal cursor;
  no following stage or main call runs before that stage's complete tool batch
  and validated artifact are available.
