# Relationship model

## Purpose

This document is the canonical functional specification for durable graph
relationships, narrative relationship context, temporal relationship states,
and how those representations are created, enhanced, and consumed.

## Three complementary representations

| Representation | Purpose | Shape | Typical use |
| --- | --- | --- | --- |
| Direct relationship | A durable, queryable connection between two resolved objects | Typed graph edge such as `KNOWS`, `WORKS_AT`, or `PARTICIPATED_IN` | Graph traversal, filtering, and compact visualization |
| `RelationshipContext` | The stable narrative identity of a meaningful relationship | Owner-scoped node connected to its resolved participants | Relationship detail, emotional meaning, and the parent of temporal history |
| `RelationshipState` | One dated or otherwise time-qualified observation about a relationship context | Append-only child node of one `RelationshipContext` | Status, closeness, emotional state, and change over time |

These representations are complementary rather than mandatory duplicates. A
simple durable fact may require only a direct edge. A rich or evolving
relationship may use a context with states and may also retain a direct edge for
efficient traversal. A context is not technically attached to a Neo4j edge:
it reifies the relationship as a node linked to the same participants.

## Supported direct relationships

The provider-facing relationship enum contains semantic edges the model may
request for the currently supported node types:

- `PARTICIPATED_IN`: person to event;
- `HAPPENED_AT`: event to place;
- `KNOWS`: person to person;
- `WORKS_AT`: person to organization;
- `OWNS`: person or organization to object;
- `OWNED_BY`: animal or object to person, organization, or social circle;
- `CARED_FOR_BY`: animal to person or organization;
- `LIVES_WITH`: person or animal to another supported household participant;
- `MEMBER_OF`: person or animal to social circle;
- `LOCATED_IN`: place to place;
- `RELATED_TO`: supported fallback only when a meaningful durable connection is
  evident but no more precise semantic edge applies.

Backend-managed structural edges such as `HAS_MEMORY_LOG`, `INVOLVES`,
`PERCEPTION_OF`, `HAS_RELATIONSHIP_CONTEXT`, `RELATIONSHIP_WITH`, and
`HAS_RELATIONSHIP_STATE` never appear as model-selectable relationship types.
Their owning persistence operations create them deterministically.

Direct relationships are owner-scoped and keyed by relationship type, source
endpoint, and target endpoint. Repeated creation reuses that edge. Existing
fields are changed only through an explicit typed update action; lookup or
repetition alone does not silently overwrite them.

## Relationship-context identity

A relationship context is identified within one owner's graph by:

- its resolved participant set;
- its normalized relationship category; and
- the owner's perspective.

Participant order does not create a second context. Direct edge direction is
still preserved separately where its semantics require direction. The initial
compact context categories are `family`, `friendship`, `romantic`,
`professional`, `community`, `caregiving`, `ownership`, `attachment`, and
`other`. More specific source wording belongs in typed descriptive fields, not
in an invented graph relationship type.

The relationship-writing state chooses the participant refs and normalized
category. The deterministic context tool reuses the exact owner, participant
set, and category key or creates it when absent. This is identity-key reuse,
not an inferred semantic merge. If the participants or category are materially
unclear, the state clarifies or defers before calling the tool.

## Initialization policy

`RelationshipWriteState` is the LLM invocation that evaluates inherited source
history, ingestion reasoning, resolved endpoints, and completed memory and
perception writes. Backend code does not infer a relationship merely because
two objects occur in the same memory.

For each supported relationship observation, the state follows this functional
order:

1. Decide whether the source supports a durable direct edge, richer context,
   both, or neither. Incidental co-presence remains `MemoryLog` involvement.
2. Request a direct edge through its typed create/update action when a durable
   semantic connection is supported.
3. Reuse or create `RelationshipContext` when the source carries narrative,
   emotional, or evolving relationship meaning that a direct edge would lose.
4. Create an initial `RelationshipState` only when the source contains a
   meaningful time-qualified condition such as current status, closeness,
   emotional state, `valid_from`, or `valid_to`. Context creation alone does not
   fabricate an empty state.
5. Link relevant created `MemoryLog` records to the context through the
   backend-owned `UPDATES_RELATIONSHIP` structural edge.

Context creation must complete before a dependent state is requested. The
state's normal provider tool loop supplies the created context ref to the next
call; no workflow-specific shortcut or fabricated ref is needed.

## Append-only enhancement policy

Later ingestion runs search for context using the same owner, participant set,
and category. A new `RelationshipState` is appended when the source provides a
new or changed time-qualified observation. Existing states are not overwritten
to make a newer account appear current.

Each state may contain a compact subset of:

- `status` and `closeness`;
- `description` or emotional summary;
- emotional valence and tags;
- original user wording when its phrasing matters;
- `valid_from`, `valid_to`, and time precision.

An exact repeated observation does not create another state. Missing dates are
kept unknown rather than invented. A newer state does not deterministically
close the prior state unless the source explicitly supplies the transition or
end time. “Current” is therefore a derived read projection: select the latest
applicable non-ended state when timing supports that conclusion, otherwise
present the history without asserting a current state.

## Consumption

Consumers use each representation according to its purpose:

- graph exploration and ordinary queries traverse direct relationships;
- a relationship detail view hydrates the context, its participants, linked
  memory logs, perceptions, and chronologically ordered states;
- retrieval returns the stable context plus a bounded set of current,
  query-relevant, or recent states rather than injecting the complete history;
- the ingestion workflow uses existing context/state packets as evidence for
  reuse or append decisions, never as permission for a deterministic semantic
  overwrite;
- user-facing rendering uses names, category, descriptions, and dates; backend
  IDs and model-local refs remain internal.

## Contract and tooling boundaries

Provider-facing DTOs use only references from the active `ReferenceContext`.
Backend-only persistence requests resolve those refs to UUIDs immediately
before calling the graph repository.

Task 4.3.5 provides three explicit capabilities:

1. create or explicitly update a supported direct relationship;
2. create or reuse a relationship context for resolved participants;
3. append a relationship state to an existing context.

The context and state operations also accept relevant existing `MemoryLog` refs
when their structural linkage is required. Tool outputs return created or
reused local refs and readable outcomes. Structural edge creation remains an
implementation detail of the deterministic repository boundary.

## Related documentation

- [Graph model](graph-model.md)
- [MemoryLog model](memory-log-model.md)
- [Temporal model](temporal-model.md)
- [Relationship write state](../ai-engineering/application-states/ingestion/relationship-write-state.md)
- [Memory-ingestion workflow map](../architecture/memory-ingestion-workflow-map.md)
