# Ingestion reasoning state

## Purpose

Interpret a source and its bounded graph context before any object is proposed
or written. This state creates useful semantic guidance for downstream states;
it does not decide persistence operations.

## Why it exists

A dense source can contain people, aliases, episodes, weak co-presence, durable
relationships, perceptions, and gaps in context. Separating this interpretation
from object creation prevents downstream states from treating every mention as a
node or every co-occurrence as a relationship.

## Required context

- normalized source or derived transcript;
- selected conversation history when it materially affects interpretation;
- bounded hydrated graph context;
- `ReferenceContext` at level 1 for known objects, plus level 2 only when
  identity evidence needs richer explanation;
- active owner projection when first-person language is relevant.

## LLM convention

The state identifies salient people, places, events, observations, aliases,
possible durable relationships, ambiguity, possible contradictions, and details
that should remain episodic or low precision. It reasons in concise semantic
notes, not hidden chain-of-thought.

It must not allocate object references, produce graph mutation commands, choose
an existing identity, create a relationship, or treat a lookup hint as a fact.
It must distinguish a possible context gap from a gap that genuinely needs user
clarification.

## Tools and clarification

The default is one structured call with no toolbox. A read-only context-expansion
toolbox may be configured only when the supplied context is insufficient for the
state's stated purpose. It never receives graph-write tools.

When a genuine unresolved gap would materially affect a later decision, the
state may surface it as structured clarification guidance for the relevant
downstream state. It does not render a user question or manage continuation on
its own.

## Expected result and handoff

The typed result is an `IngestionReasoningResultDTO`: concise semantic
highlights, useful alias observations, ambiguity/context-gap notes, durable
relationship observations, and guidance about what should remain memory-log
involvement rather than durable graph structure.

The node-candidate state receives this result as a named context section. It
does not receive the reasoning provider transcript.

## Prompt contract

The state prompt must label source, graph context, known references, and owner
projection distinctly. It must say that the result is guidance for later states
and that it must not create refs or write actions.

## Related documentation

- [Agentic state preparation](../../runtime/agentic-state-preparation.md)
- [MemoryLog model](../../../network/memory-log-model.md)
- [Clarification agent and UX](../../../requirements/functional/clarification-agent-and-ux.md)
