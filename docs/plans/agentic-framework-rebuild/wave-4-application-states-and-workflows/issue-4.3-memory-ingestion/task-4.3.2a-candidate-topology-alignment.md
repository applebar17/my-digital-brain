# Task 4.3.2a — align graph topology with candidate types

**Status: Completed**

## User story

As the ingestion workflow, I need candidate types accepted by the read-only
candidate state to have coherent graph contracts before node writes begin.

## What and why

Before Task 4.3.3 writes candidates, align the canonical graph topology and
define the target typed persistence contracts for the accepted candidate
taxonomy. In particular, migrate the existing standalone `Topic`
representation into `KnowledgeItem` and add the kinds
`topic`, `concept`, `idea`, `insight`, `reminder`, `quote`, `reference`, and
`other`.

This task does not change Task 4.3.2 candidate generation and does not add a
second candidate schema. It establishes the clean `product.graph` contract;
Task 4.3.3 binds that contract to the deterministic graph service, Neo4j
adapter, model-facing graph action, and state-specific toolbox when the first
write consumer is implemented. The deprecated agentic graph handlers are not
modified or copied.

The graph contract uses a small inherited base for fields with identical
meaning across node types and explicit subtype DTOs for type-specific data.
Every field has a concise semantic description used by later tool-schema
generation. The base must not force a generic `name` onto types for which
`display_name`, `title`, or another field has clearer domain meaning.

## Where

- Canonical graph topology and relevant network documentation.
- Target graph contracts in `src/product/graph/models.py`.
- Task 4.3.3 as the consumer that will add deterministic persistence and tool
  bindings without a second graph schema.

## Dependencies and acceptance

- Depends on Task 4.3.2's accepted candidate contracts.
- Completes before Task 4.3.3 node resolution and writes.
- One canonical node-kind definition is shared by candidate, persistence, and
  future tool contracts rather than copied between layers.
- Candidate fields map explicitly to typed backend creation fields without
  generic property bags or backend identifiers entering model context.
- The common node base contains only the node-type discriminator,
  `description`, and `aliases`; Person, Event, Place, Organization, Object,
  Animal, SocialCircle, and KnowledgeItem each own their compact
  subtype-specific fields as specified by the canonical graph model.
- `identity_gaps` remains candidate/workflow context and is not silently stored
  as a graph property.
- Topic and concept information is consistently represented through
  `KnowledgeItem`; readable presentation derives its title from the concrete
  subtype rather than requiring one ambiguous universal name field.
- The legacy `my_digital_brain.graph` implementation is not expanded in place;
  the Neo4j adapter and typed graph-action binding are introduced with the
  first target write consumer in Task 4.3.3.
