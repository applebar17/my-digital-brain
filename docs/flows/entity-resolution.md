# Entity Resolution Flow

## Purpose

Entity resolution prevents the graph from filling with duplicates and protects existing memories from incorrect merges. It decides whether a new mention refers to an existing entity, a new entity, or an unresolved candidate that needs clarification.

## Resolution Inputs

The resolution engine should consider:

- Candidate entity type.
- Extracted name and aliases.
- Source text and source metadata.
- Nearby candidate entities and relationships.
- Existing graph entities.
- Existing aliases and previous mentions.
- Time and place context.
- Embedding similarity.
- Deterministic identifiers from integrations.
- User corrections and past clarification answers.

## Match Outcomes

The engine can return:

- `match_existing`: candidate refers to one existing entity.
- `create_new`: candidate is sufficiently distinct.
- `needs_clarification`: multiple plausible matches exist.
- `keep_pending`: not enough information to decide yet.
- `reject`: candidate is invalid or not useful.
- `propose_merge`: candidate or existing entities appear duplicated but require confirmation.

In the refined ingestion baseline, these outcomes are produced before durable
entity creation. Entity candidates become either matched existing refs, staged
create/update operations, rejected candidates, or pending duplicate-review
items. Relationship planning consumes only the resulting resolved entity map.

## Resolution Stages

1. Receive entity candidates after the structured reasoning and entity planning
   stages.
2. Normalize candidate fields such as names, dates, places, and aliases.
3. Compare candidates with the pre-retrieved `GraphContextPack` and current
   graph state.
4. Search for deterministic matches from external IDs or exact aliases.
5. Search for fuzzy matches using names, embeddings, and graph context.
6. Score candidates with explainable match reasons.
7. Apply policy thresholds.
8. Return a resolved entity map with matched existing refs, staged creates,
   staged updates, rejected candidates, and pending duplicate-review items.
9. Ask clarification if confidence is insufficient or the action is risky.
10. Write the selected resolution decision with provenance only when the
    downstream write process is allowed to proceed.

## Duplicate Judge Slot

Duplicate handling is a required process slot before durable entity writes.

Wave 1 keeps this conservative and deterministic:

- exact name matches;
- exact alias matches;
- unsupported duplicate fields rejected by schema validation;
- local ref collisions rejected;
- obvious exact duplicate candidates collapsed or staged.

Later waves may introduce a qualitative duplicate judge that compares new
candidates with current graph state and decides:

```text
confirmed duplicate -> update existing node
suspected duplicate -> ask user confirmation
not duplicate -> create new node
```

When a duplicate is confirmed, useful information should transfer to the
canonical node instead of creating a parallel entity:

- aliases;
- relationships;
- additional metadata;
- log or activity references;
- refreshed embeddings.

## Homonymous People

When multiple people share the same or similar name, the system should ask a targeted question rather than guess.

Example:

```text
Which Marco do you mean: Marco Rossi from work, Marco Bianchi from university, or someone new?
```

The user answer should become resolution evidence and should improve future matches.

## Incomplete Places

Places should support different precision levels:

- Country.
- Region.
- City.
- Neighborhood.
- Venue.
- Address.
- Coordinates.

If the user says an event happened in Italy, the graph can store Italy as a low-precision place, but the system should ask for a more specific place when it materially improves the memory.

## Event Deduplication

Events are difficult because the same event may be described multiple times.

Signals for duplicate events:

- Similar time window.
- Similar participants.
- Similar location.
- Similar topic.
- Repeated source content.
- Similar event summary embedding.

The system should avoid merging events automatically unless confidence is high. It is better to keep two related events than to incorrectly collapse separate memories.

## Merge And Split

Merges should be reversible or at least auditable.

`MergeRecord` is a graph audit object created when two or more nodes are judged to represent the same real-world entity.

Example:

- The graph has `Person: Marco from university`.
- Later the user mentions `Marco Bianchi`.
- Evidence shows these are the same person.
- The system creates or proposes a merge into one canonical `Person`.

Merge records should preserve:

- Original entity IDs.
- Canonical entity ID.
- Merge reason.
- User or system actor.
- Timestamp.
- Source evidence.
- Status: proposed, applied, reverted.

Purpose:

- Explain why identity unification happened.
- Make incorrect merges debuggable.
- Prepare for future split or revert behavior.
- Avoid silent graph corruption.

Splits should be supported later to recover from incorrect merges. Until then, risky merges should remain proposed or require user confirmation.

## Applying A Merge

Applying a merge should be non-destructive.

Recommended behavior:

- Select a canonical node.
- Create a `MergeRecord`.
- Link all merged nodes to the merge record.
- Link the canonical node to the merge record.
- Add `MERGED_INTO` from each merged node to the canonical node.
- Mark merged nodes as archived instead of deleting them.
- Copy safe aliases and source references to the canonical node.
- Do not silently overwrite canonical fields with conflicting values.
- Create `ChangeRecord` entries for lifecycle changes and canonical field changes.

This makes the merge useful immediately while preserving identity history and leaving room for future split/revert behavior.

## Resolution Evidence

Each decision should be explainable:

- Matched alias.
- Shared source.
- Shared participants.
- Embedding score.
- User clarification answer.
- External ID match.
- Manual confirmation.

This evidence is useful for debugging, frontend review, and future automated improvements.
