# Interrogation flow

## Purpose

Interrogation lets a user ask about their memory through natural language,
structured inspection, or graph navigation. Answers are grounded in retrieved
graph facts and source evidence, with uncertainty made clear when memory is
missing, incomplete, inferred, or disputed.

## Query modes

- **Natural language:** ask a question, request a summary or comparison, or
  explore a person, event, place, relationship, or period.
- **Structured inspection:** use advanced graph-oriented queries or filters
  when that capability is intentionally exposed.
- **Visual navigation:** open focused graph neighborhoods, timelines, maps,
  sources, evidence, and related memory details.

## Functional journey

```text
user question
  -> relevant graph memory is retrieved and hydrated
  -> evidence, time, relationships, and affective context are considered
  -> grounded answer and optional focused graph view are returned
  -> user may refine, navigate, or correct the result
```

Semantic retrieval identifies candidate pointers; graph hydration establishes
the facts available to an answer. The system does not present a vector hit as
memory truth by itself.

## Answer expectations

- Ground answers in retrieved graph records and source evidence.
- State uncertainty, missing context, inferred information, and material
  conflicts when they affect the answer.
- Include emotional or perceptual context only when relevant, and distinguish
  user-stated content from inference where possible.
- Treat `MemoryLog` hits as gateways to their hosts, involved targets, and
  context; normal graph views focus on hydrated domain objects.
- Do not mutate memory while answering a question. A correction or new memory
  follows the ingestion flow.

## Visualization handoff

When useful, interrogation returns a focused result for the UI: seed objects,
related objects and relationships, evidence references, relevant timeline
grouping, location grouping, and safe display-oriented ranking information. It
must not return the entire graph, raw vector payloads, or backend identifiers.

## Examples

- What do I know about Marco Rossi?
- Who was involved in the dinner where we discussed the new project?
- Show memories connected to Milan in 2025.
- What happened with Alessandro?
- What emotional memories do I associate with that period?
- Do I have conflicting information about where that meeting happened?

## Related documentation

- [Memory query state](../ai-engineering/application-states/memory-query-state.md)
- [Vector retrieval and indexing](../network/vector-retrieval.md)
- [Context package contract](../ai-engineering/context-and-prompts/context-package-contract.md)
- [Frontend UI product requirements](../requirements/ui/frontend-ui-product-requirements.md)
- [MemoryLog model](../network/memory-log-model.md)
