# Entity resolution flow

## Purpose

Entity resolution helps the system avoid duplicate graph objects without
incorrectly collapsing distinct people, places, events, or organizations. It
determines whether available evidence supports reuse of a known object, a new
object, clarification, deferral, or a future user-confirmed merge.

## Functional decision boundary

The backend gathers bounded identity evidence using deterministic lookup,
normalization, and permitted graph context. The LLM state interprets that
evidence with the current source and decides the semantic outcome. The backend
then validates the supplied references and carries out only the supported typed
operation.

Neither side silently merges identities: lookup is not an automatic identity
binding, and a model cannot invent an object reference or persisted ID.

## Resolution evidence

Useful evidence may include:

- type, readable name, and useful aliases;
- source wording and prior user clarification;
- time, place, participants, and nearby memory context;
- deterministic external identifiers when supported;
- clearly labelled similarity or retrieval hints;
- prior source/evidence links and manual confirmation.

Model-facing evidence is supplied through the active `ReferenceContext`; it
contains readable references and selected context, never raw backend IDs.

## Expected outcomes

- **Reuse an existing object:** supplied evidence identifies one known object.
  New information is normally attached additively through memories, context, or
  relationships rather than overwriting identity fields.
- **Create a new object:** no supplied known object is sufficiently identified.
- **Ask clarification:** several plausible objects exist, or an identity gap
  would make a durable write unreliable.
- **Defer:** the fact can be preserved without resolving the identity now, or
  the missing decision has low value.
- **Reject:** the proposed object is invalid, unsupported, or not useful.
- **Propose a merge:** two persisted records may represent one real-world
  entity. This remains a future, explicit, user-confirmed operation.

## Common scenarios

### Similarly named people and aliases

When several people could match "Marco," the system asks a distinguishing,
natural question rather than guessing. Nicknames, short names, and role phrases
are evidence to investigate, not automatic separate entities or durable aliases.

### Incomplete places

Places can be preserved at country, region, city, neighborhood, venue, address,
or coordinate precision. The system asks for more detail only when it changes
the usefulness or identity of the memory.

### Repeated events

The system considers time, participants, location, topic, source wording, and
related memories. It prefers preserving two related events over incorrectly
collapsing distinct episodes.

## Merge and split

Merge and split are future maintenance behaviors, not ordinary ingestion steps.
A merge requires meaningful evidence, explicit confirmation, an audit record,
and preservation of the original records for traceability and potential revert.
Conflicting field values must not silently overwrite the chosen canonical
object. A split remains available as the recovery path for an incorrect merge.

## Related documentation

- [Node candidate state](../ai-engineering/application-states/ingestion/node-candidate-state.md)
- [Node resolution and write state](../ai-engineering/application-states/ingestion/node-resolution-write-state.md)
- [Reference context and owner projection](../ai-engineering/context-and-prompts/reference-context-and-owner-projection.md)
- [Clarification agent and UX](../requirements/functional/clarification-agent-and-ux.md)
- [Memory lifecycle](../network/memory-lifecycle.md)
