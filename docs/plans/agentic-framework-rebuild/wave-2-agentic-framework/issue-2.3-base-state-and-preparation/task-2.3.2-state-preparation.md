# Task 2.3.2 — configure reasoning and planning preparation

**Status: Not started**

## User story

As a concrete state, I want to opt into structured reasoning and/or planning
with the relevant conversation context, so preparation improves that state's
main call without forcing every state through extra LLM calls.

## What and why

Implement only the configured preparation options specified by the runtime
docs. Reasoning is independent; planning may consume the reasoning artifact.
Toolboxes are optional configuration, and default preparation calls are
one-shot without tools. No hidden-reasoning output or mandatory multi-stage
pipeline is introduced.

## Where

- `src/product/agentic/` preparation configuration and typed artifacts.
- Concrete state opts in from `product.application.states` when its functional
  spec requires it.

## Functional communication DTOs

Preparation receives the selected history/context and request. Reasoning returns
a typed `ReasoningArtifact`; planning receives that artifact when available and
returns a typed `PlanArtifact` for the owning state to use. Artifacts stay
internal unless the state contract explicitly returns them.

## Dependencies and acceptance

- Depends on Task 2.3.1 and the accepted preparation specification.
- Disabled preparation adds no calls or output fields.
- Planning consumes reasoning only when configured and available.
- Main state receives the artifacts as explicit context, not as a forged
  assistant transcript turn.
