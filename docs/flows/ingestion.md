# Ingestion Flow

## Purpose

The ingestion flow turns user input into graph updates while preserving source evidence, handling ambiguity, and avoiding duplicate entities.

## Basic Flow

1. User sends a message through Telegram or another channel.
2. System stores the raw message as a `Source`.
3. LLM extraction proposes structured ingestion objects: candidate entities, relationships, claims, metadata patches, dates, places, and missing fields.
4. Validator checks schema, confidence, and required information.
5. Resolution engine searches for existing graph matches.
6. Clarification manager asks follow-up questions if needed.
7. User replies to clarification questions.
8. System updates candidates with the answers.
9. Graph writer persists entities, relationships, evidence links, and embeddings.
10. User receives a concise ingestion summary when useful.

## Example

User:

```text
Yesterday I had dinner with Marco and Giulia in Italy. We talked about the new project.
```

Possible system questions:

```text
Which Marco do you mean: Marco Rossi from work, Marco Bianchi from university, or someone new?
```

```text
Where in Italy did the dinner happen?
```

Potential graph output:

- Event: dinner.
- People: Marco, Giulia, user.
- Place: clarified city or venue.
- Topic: new project.
- Relationships: people participated in event, event happened at place, event was about topic.
- Source: original Telegram message plus clarification replies.

## Candidate Graph

Before writing to the canonical graph, extraction should produce a candidate graph:

- Candidate nodes.
- Candidate relationships.
- Confidence scores.
- Evidence references.
- Missing fields.
- Ambiguity markers.
- Suggested clarification questions.

This allows validation and resolution before permanent graph writes.

The candidate graph should be represented through structured ingestion objects rather than free-form model output. See [Structured ingestion objects](structured-ingestion-objects.md).

## Clarification Policy

Ask clarification when:

- A candidate maps to multiple high-probability existing entities.
- A required field is missing for a useful memory.
- The location, date, or participant set is too vague.
- There is a conflict with existing graph facts.
- The write would merge entities.
- The source contains sensitive information and policy requires confirmation.
- The system found a contact detail or external enrichment candidate that may affect future integrations.

Do not ask clarification when:

- The missing detail is not important to the memory.
- The user can reasonably fill it later.
- The answer can be represented as low precision.
- The system can store the fact as uncertain without damaging identity resolution.

## Duplicate Prevention

Before creating new entities, the system should search for:

- Exact matches.
- Alias matches.
- Similar names.
- Similar embeddings.
- Nearby events in time and place.
- Repeated source content.
- Common participants.
- Existing unresolved candidates.

Potential duplicates should be staged for confirmation when confidence is not high enough.

## Idempotency

Each source should have a stable identifier. Reprocessing the same source should update the same extraction run or create a new version linked to the same source, not create duplicate graph facts.

## Failure States

The ingestion flow should explicitly track:

- Received.
- Stored.
- Extracted.
- Needs clarification.
- Waiting for user.
- Resolved.
- Written.
- Failed validation.
- Failed graph write.
- Superseded by correction.
