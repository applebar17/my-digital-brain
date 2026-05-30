# Ingestion Flow

## Purpose

The ingestion flow turns user input into graph updates while preserving source evidence, handling ambiguity, and avoiding duplicate entities.

## Basic Flow

1. User sends a message through Telegram or another channel.
2. System stores the raw message as a `Source`.
3. LLM extraction proposes structured ingestion objects: candidate entities, relationships, claims, perceptions, relationship contexts, emotional summaries, metadata patches, dates, places, and missing fields.
4. Validator checks schema, confidence, and required information.
5. Resolution engine searches for existing graph matches.
6. Context builder retrieves nearby graph context for proposed writes.
7. Memory-writing agent reviews the proposal against current state, relevant history, sources, relationship contexts, perceptions, place/time context, and similar entities.
8. If the agent has a grounded contradiction doubt, it invokes the contradiction judge tool with the proposal, retrieved context, and explanation.
9. The AI Manager asks a follow-up question if useful.
10. If clarification is needed, the latest ingestion session for the Telegram chat is marked as waiting.
11. The user's next relevant message is appended to that pending ingestion session.
12. The AI Manager resumes the ingestion dynamically.
13. Graph writer persists entities, relationships, evidence links, and embeddings.
14. User receives a concise ingestion summary when useful.

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
- Affective memory: emotional tone, user-stated perceptions, original wording, or relationship context for any memory-bearing target if present in the source.
- Source: original Telegram message plus clarification replies.

## Candidate Graph

Before writing to the canonical graph, extraction should produce a candidate graph:

- Candidate nodes.
- Candidate relationships.
- Candidate perceptions.
- Candidate relationship contexts.
- Emotional summaries and original user wording when present.
- Confidence scores.
- Evidence references.
- Missing fields.
- Ambiguity markers.
- Retrieved context used for write review.
- Agent contradiction doubts when present.
- Suggested clarification questions.

This allows validation and resolution before permanent graph writes.

The candidate graph should be represented through structured ingestion objects rather than free-form model output. See [Structured ingestion objects](structured-ingestion-objects.md).

## Clarification Policy

Clarification is an agentic behavior inside the ingestion loop. It is not a standalone public API, workflow engine, or fully deterministic process.

Ask clarification when:

- A candidate maps to multiple high-probability existing entities.
- A required field is missing for a useful memory.
- The location, date, or participant set is too vague.
- There is a conflict with existing graph facts.
- The write would merge entities.
- The source contains sensitive information and policy requires confirmation.
- The system found a contact detail or external enrichment candidate that may affect future integrations.
- The contradiction judge decides a suspected conflict would make future answers unreliable.

Contradiction clarification should usually come from the contradiction judge decision, not from a fixed deterministic rule.

Do not ask clarification when:

- The missing detail is not important to the memory.
- The user can reasonably fill it later.
- The answer can be represented as low precision.
- The system can store the fact as uncertain without damaging identity resolution.
- The clarification would interrupt memory capture more than it would improve memory quality.

## Clarification Fatigue Policy

The system should avoid turning ingestion into mechanical review.

Preferred behavior:

- Ask one focused question at a time.
- Ask mostly for contradictions, risky merges, sensitive data, and important ambiguity.
- Preserve low-precision memories when that is good enough.
- Let the user skip clarification.
- Use natural follow-up conversation to improve memory quality over time.

The goal is to retain the user in a useful conversation, not to force complete data entry.

## Agentic Contradiction Suspicion

Contradiction handling is not a deterministic rule engine.

Before writing candidate memory, the system should provide the memory-writing agent with focused graph context. The agent can then notice a possible contradiction in natural semantic context.

Example:

```text
New proposal: "the dinner with Marco happened in Milan."
Retrieved context: the same event currently has location Turin.
Agent doubt: "This appears to be the same dinner, but the location differs."
```

In that case, the memory-writing agent may invoke the contradiction judge tool.

The judge receives:

- proposed write
- retrieved context
- affected entities and relationships
- source references
- the agent's explanation of the doubt

The judge may use read-only graph tools to inspect more context. It returns a structured decision:

- no_conflict
- nuance
- temporal_update
- contradiction
- needs_clarification

The judge may recommend allowing the write, writing the new fact as disputed, creating a `ContradictionRecord`, creating a `RelationshipState`, or asking the user a clarification.

Deterministic code should only provide guardrails: context retrieval, schema validation, tool limits, permission boundaries, and persistence of auditable judge decisions.

## Pending Ingestion State

The MVP should persist only the state needed to resume an interrupted or waiting ingestion.

Minimal state:

- `ingestion_session_id`
- `telegram_chat_id`
- `status`
- `pending_question`
- `candidate_graph_snapshot`
- `expires_at`
- `updated_at`

When a new Telegram message arrives, the AI Manager checks whether the chat has a waiting ingestion. If yes, the message can be interpreted as the clarification answer and appended to that session. If not, the message starts a new ingestion or query flow.

The AI Manager can still decide that a message is not a valid clarification answer and can use tools such as skip, restart, expire, or ask another clarification. The MVP does not need to handle every edge case explicitly before it appears in real usage.

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
