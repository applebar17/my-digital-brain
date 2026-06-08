# Ingestion Flow

## Purpose

The ingestion flow turns user input into graph updates while preserving source evidence, handling ambiguity, and avoiding duplicate entities.

## Refined Baseline Flow

1. User sends a message through Telegram or another channel.
2. System stores the raw message as a `Source`.
3. If the source is audio, speech-to-text creates a transcript source linked to the original audio.
4. For wave-1 refinement, backend retrieval embeds the whole source text and
   retrieves top-k relevant graph items through hybrid search.
5. Backend code compacts the hydrated retrieval result into a model-facing
   `GraphContextPack`.
6. A structured reasoning checkpoint receives source text, usable conversation
   context when relevant, current time/timezone, and the `GraphContextPack`.
7. The reasoning checkpoint returns structured interpretation: entity
   understanding, aliases, duplicate concerns, relationship hypotheses,
   user/owner involvement, node-versus-metadata recommendations, ambiguity, and
   storage cautions.
8. The reusable planning primitive receives the source, graph context,
   entity-focused reasoning, and entity-planning guidelines, then returns an
   entity-only plan.
9. Entity candidate preparation creates schema-compatible entity drafts with
   local refs, aliases, property suggestions, evidence text/spans, missing
   fields, and ambiguity flags.
10. Backend entity validation and duplicate handling run before durable entity
   creation. In wave 1 this step is deterministic and conservative.
11. Backend code produces a resolved entity map that links local refs to
   existing graph aliases or staged create/update operations.
12. The reusable planning primitive receives the source, relationship-focused
   reasoning, compact graph relationships, relationship-planning guidelines,
   and the resolved entity map.
13. Relationship candidate preparation creates relationships, relationship
   contexts, perceptions, event links, place links, or metadata suggestions only
   against resolved refs.
14. If a required relationship endpoint is missing, the relationship step emits
   `missing_entity_required`, which loops back into supplemental entity
   candidate handling.
15. Backend relationship validation checks schema, allowed ontology values,
   resolved endpoints, forbidden fields, and exact duplicate edges.
16. Backend services assemble and execute a validated `GraphWritePlan`.
17. If clarification is needed, the ingestion session stores a pending process
   context.
18. Later chat messages are processed with that pending context and
   conversation history available. The AI Manager can classify a later message
   as a clarification answer, new memory, question, cancellation, correction, or
   normal chat, then resume ingestion only when appropriate.
19. User receives a concise ingestion summary when useful.

The dedicated wave-1 implementation plan is
[Ingestion reasoning refinement wave 1](../dev-plans/10-ingestion-reasoning-refinement-wave-1.md).
Generated natural-language graph query fan-out is intentionally out of scope
for the first refinement baseline; whole-source hybrid retrieval is the v1
context strategy.

LLM-backed steps return draft objects, not backend records. The model extracts
semantic content, evidence text/spans, local candidate refs, and graph aliases.
Backend code then enriches those drafts with source IDs, generated IDs,
`EvidenceRef`, status fields, timestamps, and metadata before validation,
resolution, or graph writes.

The planner does not choose database ontology. In the refined baseline, entity
planning and relationship planning are separate model tasks. Entity planning
decides which entities, aliases, and entity-like details require candidate
preparation. Relationship planning runs only after entity validation has
produced a resolved entity map, then decides which relationships or
relationship-like memory objects require candidate preparation.

The backend compiler decides which extractor schema to call and what refs are
available to that call.

DB-facing extraction is enum/ref constrained. LLM-creatable entity labels are:
`Person`, `Event`, `Place`, `Organization`, `Object`, `Animal`,
`SocialCircle`, and `Topic`. Social relationships use `RELATIONSHIP_WITH` plus
`relationship_kind`:

```text
friend | family | partner | former_partner | colleague | classmate | acquaintance
```

Specific wording is preserved in details and property suggestions, not in new
labels or edge types. For example, "brother" becomes
`relationship_kind=family` and `relationship_detail=brother`; "girlfriend"
becomes `relationship_kind=partner` and `relationship_detail=girlfriend`.

## LLM Action Boundary

The conversational LLM chooses actions and proposes parameters. Backend services validate and execute.

Allowed top-level conversational actions are intentionally few:

- default answer path: no tool
- `start_memory_ingestion`
- `query_memory_context`
- `propose_memory_correction`

Resume, cancel, expire, clarification handling, validation, and graph write execution are backend process states or internal services. They are not broad top-level tools.

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
- Source: original chat message plus relevant clarification replies.

## Candidate Graph

Before writing to the canonical graph, extraction should produce a candidate graph. The graph write plan is deterministic backend output after validation and resolution; it is not a separate LLM-authored graph mutation.

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

Every LLM draft extraction object should include enough grounding to debug or reject it:

- evidence text/spans
- original user words when present
- missing fields
- ambiguity flags
- clarification need

Backend-enriched candidate records add source references and evidence refs after
the draft is validated.

This allows validation and resolution before permanent graph writes.

In the refined baseline, the candidate graph is assembled in stages:

1. entity candidates first;
2. deterministic entity validation and duplicate handling;
3. resolved entity map;
4. relationship candidates using only resolved refs;
5. deterministic relationship validation.

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
- `conversation_id`
- `channel`
- `status`
- `pending_question`
- `pending_process_context`
- `conversation_history_refs`
- `candidate_graph_snapshot`
- `expires_at`
- `updated_at`

When a new chat message arrives, the AI Manager can load pending process context for that conversation and pass it into the next runtime or agent call. The pending context does not force the message to be a clarification answer. It gives the system enough context to decide whether to resume the pending ingestion, start a new ingestion, answer a question, apply a cancellation, or route to another process.

The AI Manager can still decide that a message is not a valid clarification answer and can use tools such as skip, restart, expire, or ask another clarification. The MVP does not need to handle every edge case explicitly before it appears in real usage.

## Duplicate Prevention

Before creating new entities, the system should search or compare against:

- Exact matches.
- Alias matches.
- Similar names.
- Similar embeddings.
- Nearby events in time and place.
- Repeated source content.
- Common participants.
- Existing unresolved candidates.

Potential duplicates should be staged for confirmation when confidence is not high enough.

Wave 1 reserves a duplicate-judge process slot before durable entity creation,
but only simple deterministic checks are required initially. Later qualitative
judging should decide whether a candidate is a confirmed duplicate, suspected
duplicate requiring user confirmation, or a new entity. When a duplicate is
confirmed, aliases, useful relationships, metadata or activity references, and
embedding refreshes should apply to the canonical existing node instead of
creating a new node.

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
