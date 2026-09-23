# MemoryLog model

## Purpose

A `MemoryLog` is a compact, source-backed memory atom: one coherent
observation, episode, update, or contextual detail. It complements durable
domain nodes and relationships rather than replacing them.

## Functional model

A log has a concise generated title for user-facing lists, a short summary,
source/evidence links, relevant time information, one primary host, and zero or
more involved targets. It may also link to a place, event, perception, claim,
relationship context, or media when those links are supported by the source.

The primary host anchors the log for retrieval and detail views. Involved
targets preserve meaningful participation without turning incidental
co-presence into durable relationships.

The backend enriches any model proposal with persistent identifiers,
provenance, lifecycle fields, timestamps, and validated resolved references.
The LLM never receives or creates those backend fields.

## Write and update rules

- A new observation normally creates a new `MemoryLog`; it does not silently
  overwrite a person, event, or relationship property.
- A direct patch to an existing domain object requires its own explicit typed
  update contract and evidence basis.
- A relationship is created only when the source supports a durable connection;
  weak co-presence stays as `MemoryLog` involvement.
- A log may be split from a dense source when the source contains distinct
  coherent episodes. It must not be split mechanically without semantic value.

## Rendering and retrieval

`MemoryLog` is not a default graph-workspace node. Normal exploration shows its
hydrated host and related domain objects; a selected object exposes associated
logs through a timeline or detail layer. The concise title is used in memory
lists instead of a UUID or the full log text.

Substantive logs may be vectorized using the shared deterministic index
contract. A matching log is hydrated with its host, involved targets, and
relevant context before it contributes to an answer or graph view.

## Boundaries

The graph/domain model owns the persisted log and links. State DTOs own any
model-facing proposal fields. The ingestion workflow owns ordering and context
handoff; prompts only guide the model about when a log is useful.

## Related documentation

- [Graph model](graph-model.md)
- [Vector retrieval and indexing](vector-retrieval.md)
- [Ingestion flow](../flows/ingestion.md)
