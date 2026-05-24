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

## Resolution Stages

1. Normalize candidate fields such as names, dates, places, and aliases.
2. Search for deterministic matches from external IDs or exact aliases.
3. Search for fuzzy matches using names, embeddings, and graph context.
4. Score candidates with explainable match reasons.
5. Apply policy thresholds.
6. Ask clarification if confidence is insufficient or the action is risky.
7. Write the selected resolution decision with provenance.

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

Merge records should preserve:

- Original entity IDs.
- Merged entity ID.
- Merge reason.
- User or system actor.
- Timestamp.
- Source evidence.

Splits should be supported later to recover from incorrect merges. Until then, risky merges should require confirmation.

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
