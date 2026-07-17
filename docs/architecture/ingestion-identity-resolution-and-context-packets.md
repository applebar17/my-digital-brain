# Ingestion Identity Resolution And Context Packets

## Status

Design agreed for implementation. This document captures the behavior discussed for resolving planned entities against existing graph nodes before extraction and write planning.

## Purpose

When a user mentions an entity, the ingestion pipeline must give the LLM enough bounded graph context to decide whether the entity is:

- an existing graph node;
- a new node;
- an existing node that needs new memories or relationships;
- or an unresolved/ambiguous reference requiring clarification.

The LLM may make the semantic resolution decision, but it does not execute graph queries, generate Cypher, or directly mutate the graph. Backend services own lookup, reference mapping, validation, and execution.

Example:

> I had dinner with Marco.

The planner proposes `Marco` as a Person candidate. The backend searches the graph and finds `Marco Bianchi`, `Marco Verdi`, and `Marco Rossi`. The extractor receives those candidates with bounded related context and decides whether it can proceed or must ask the user which Marco was intended.

## Core Principles

1. **Lookup is backend-owned.** The LLM requests identity lookup through structured proposal data. It never produces Cypher or an executable graph query.
2. **Planning and identity resolution are separate.** The planner describes the entity and the fields useful for lookup. The backend performs lookup before extraction.
3. **Search is deterministic.** Name and alias lookup may return candidates using deterministic normalization and bounded matching. Semantic similarity is evidence only and cannot automatically bind an entity.
4. **The extractor is autonomous within explicit boundaries.** It may select an existing candidate, request clarification, or keep the entity as new when the packet supports that decision.
5. **Graph execution remains backend-owned.** An LLM decision is a proposal. The backend validates its references and converts it into an authorized write plan.
6. **References are run-scoped.** Model-facing references are aliases valid for the current ingestion run. They are never persisted as graph IDs and never become a substitute for backend identity validation.
7. **Context is bounded.** Candidate context contains only relevant, permitted information needed for disambiguation. It must not expose the entire graph neighborhood or unrestricted memory history.

## Pipeline Position

The identity-resolution stage is inserted after entity planning and before entity extraction:

```text
source
  -> reasoning/planning
  -> planned entity candidates
  -> backend identity lookup
  -> candidate context packet
  -> entity and memory extraction
  -> resolution proposal validation
  -> graph write planning
  -> backend execution
```

The existing broad whole-source retrieval remains useful for general reasoning. It is not a replacement for per-candidate identity lookup. The new stage gives every planned node proposal a deterministic lookup result and a focused context packet.

## Multi-Wave Implementation Plan

The implementation is intentionally split into independent waves. Each wave
must preserve the existing ingestion path unless the new identity-resolution
behavior is explicitly enabled for that process.

### Wave 0: Contract And Boundary Lock

**Scope:** backend contracts, invariants, reference semantics, and test
fixtures. No production LLM behavior changes.

**Deliverables:**

- Add typed contracts for:
  - `EntityLookupRequest`;
  - `EntityLookupCandidate`;
  - `EntityLookupResult`;
  - `EntityLookupContextPacket`;
  - `EntityResolutionProposal`;
  - clarification state and response handoff.
- Define the allowed lookup statuses and resolution actions from this
  document.
- Define the run-scoped reference registry contract:
  - model-facing reference to persisted graph ID;
  - persisted graph ID to model-facing reference;
  - object kind and label validation;
  - proposed versus existing status;
  - graph/session ownership.
- Preserve `OWNER` as a reserved reference that resolves only through the
  canonical owner manager.
- Establish packet-rendering rules that exclude persisted IDs and backend
  metadata from LLM payloads.
- Add representative fixtures for:
  - no matching node;
  - one matching node;
  - several people sharing a first name;
  - fuzzy-only results;
  - owner and first-person references.

**Required invariants:**

- The LLM cannot provide an executable graph query.
- A model-facing reference is valid only if it exists in the current registry.
- A proposed entity reference cannot be treated as an existing graph node
  without an explicit backend resolution.
- `OWNER` cannot be replaced by a user-provided graph ID.

**Exit criteria:** contracts and reference invariants are tested, and the
existing ingestion behavior remains unchanged.

### Wave 1: Canonical Reference Registry

**Scope:** unify the existing alias mechanisms before adding new lookup
results to prompts.

**Deliverables:**

- Implement one run-scoped registry for existing hydrated nodes,
  relationships, memories, context objects, and proposed candidates.
- Reuse the current candidate references such as
  `CANDIDATE_PERSON_001`.
- Reconcile the current uppercase graph-context aliases such as
  `NODE_000001` with the lowercase agentic reference conventions. The
  application must expose one canonical format to each LLM process instead
  of introducing a third alias scheme.
- Ensure the same existing-node reference is reused across entity, memory,
  relationship, and clarification packets within one run.
- Keep the private alias-to-persisted-ID map available only to backend
  validation and execution.
- Remove persisted graph IDs from all model-facing renderers involved in this
  feature.

**Tests:**

- alias allocation and deterministic reuse;
- object-kind validation;
- proposed versus existing reference status;
- rejection of invented, stale, cross-run, and cross-graph references;
- correct `OWNER` mapping;
- consistent endpoint references in relationship packets.

**Exit criteria:** every graph object exposed to the LLM is represented by a
single validated run-scoped reference, and all existing reference consumers
can use the registry.

### Wave 2: Deterministic Identity Lookup

**Scope:** backend lookup service and extraction-stage integration point. No
new LLM decision behavior yet.

**Deliverables:**

- Extract the reusable deterministic matching logic from
  `ConservativeResolutionService` into an owner- and graph-scoped identity
  lookup service.
- Build lookup requests from planned entity fields rather than from raw LLM
  queries.
- Implement label-constrained lookup for identity fields:
  - display name;
  - name;
  - normalized name;
  - aliases;
  - deterministic name tokens for partial names.
- Classify results as `no_candidates`, `one_candidate`,
  `multiple_candidates`, or `fuzzy_candidates_only`.
- Keep fuzzy and semantic retrieval as non-binding hints.
- Exclude the canonical owner from ordinary Person lookup. First-person
  references resolve directly to `OWNER`.
- Cache or carry the lookup result forward so final resolution does not apply
  a different search policy.

**Tests:**

- `Marco` returns all relevant Marco candidates;
- full names and aliases match correctly;
- unrelated labels are excluded;
- one, multiple, fuzzy-only, and empty results are classified correctly;
- owner exclusion and first-person owner resolution;
- backend failure does not silently trigger duplicate creation.

**Exit criteria:** a planned entity can be looked up deterministically before
extraction, with no LLM-generated Cypher and no graph mutation.

### Wave 3: Bounded Candidate Context Packets

**Scope:** candidate hydration, redaction, packet rendering, and prompt
context delivery. The extractor still follows the existing output behavior
until Wave 4.

**Deliverables:**

- Hydrate a bounded context packet for each lookup candidate.
- Include only relevant context, such as:
  - permitted names and aliases;
  - concise relationship summaries;
  - relevant MemoryLog summaries;
  - place, organization, event, and temporal hints;
  - permitted source evidence.
- Apply existing lifecycle, visibility, privacy, and owner-scope policies.
- Cap the number of candidates, related objects, and text length.
- Mark exact, token, fuzzy, and semantic evidence explicitly.
- Delimit original user wording and mark it as user data, not instructions.
- Add purpose-specific rendering for planner and extractor contexts.
- Continue sending only the minimal owner snapshot in generic contexts.

**Tests:**

- three Marco candidates receive separate references and separate context;
- raw graph IDs and backend metadata are absent;
- unrelated neighbors are omitted;
- context limits are enforced;
- hidden or disallowed evidence is excluded;
- the same candidate reference is preserved across all packets.

**Exit criteria:** the extractor can receive a safe, bounded overview of
possible existing nodes without receiving direct database identity data.

### Wave 4: Autonomous LLM Resolution Proposals

**Scope:** planner and extractor prompts, structured outputs, and validation
of LLM-selected outcomes.

**Deliverables:**

- Teach the planner to describe lookup fields and candidate identity without
  generating queries.
- Add the candidate packet to every extraction process that can create or
  reference graph nodes.
- Teach the extractor the allowed outcomes:
  - `CREATE_NEW`;
  - `ATTACH_TO_EXISTING`;
  - `REQUEST_CLARIFICATION`;
  - `IGNORE_OR_DEFER`.
- Require existing-node attachment to reference only a supplied alias.
- Require evidence-based reasoning for selecting one of several candidates.
- Instruct the extractor that fuzzy matches are not confirmed facts.
- Prevent direct Person-property mutation as an implicit result of identity
  matching.
- Add backend validation that rejects invented aliases, invalid labels,
  owner impersonation, and unsupported actions.

**Tests:**

- no-candidate extraction can propose a new entity;
- a sufficient single-candidate packet permits attachment;
- ambiguous packets produce clarification instead of silent selection;
- fuzzy-only context cannot produce an automatic attachment;
- invalid or invented references are rejected;
- owner relationships use `OWNER` as the endpoint;
- unrelated extraction flows retain their current behavior.

**Exit criteria:** the extractor can autonomously choose a safe resolution
outcome using the packet, while every outcome remains backend-validated.

### Wave 5: Clarification And Update-Agent Handoff

**Scope:** user clarification lifecycle and handoff from extraction to graph
update planning.

**Deliverables:**

- Persist compact clarification state containing:
  - original candidate;
  - candidate packet;
  - proposed graph effects;
  - question and evidence;
  - owner and graph scope;
  - expiration or retry metadata where applicable.
- Render human-readable clarification questions without exposing internal
  references or persisted IDs.
- Re-enter the pipeline with the original candidate and the user's answer.
- Allow the extractor after clarification to:
  - create a new node;
  - attach to a supplied existing node;
  - request another clarification;
  - defer the entity.
- Define the update-agent handoff as a structured proposal, not a second
  independent identity lookup.
- Revalidate the selected existing node immediately before write planning.
- Translate `ATTACH_TO_EXISTING` into additive memory, relationship, claim,
  perception, or relationship-context operations.
- Keep direct Person patches explicit, separately authorized, and
  provenance-backed.

**Tests:**

- clarification selects an existing node;
- clarification selects new-node creation;
- clarification remains unresolved safely;
- user answers cannot inject arbitrary references;
- stale graph state is revalidated;
- attached events create the expected MemoryLog and relationship;
- update-agent handoff does not repeat or contradict identity resolution.

**Exit criteria:** a complete ambiguous-entity workflow can move from lookup
to user clarification to validated graph write without duplicate creation or
unscoped mutation.

### Wave 6: Hardening, Evaluation, And UAT

**Scope:** production hardening, observability, regression coverage, and
interactive ingestion validation.

**Deliverables:**

- Add structured trace events for:
  - lookup request;
  - lookup classification;
  - candidate packet creation;
  - LLM resolution proposal;
  - clarification request and response;
  - backend validation decision;
  - final write-plan effects.
- Ensure traces redact persisted graph IDs from LLM-facing payload views while
  retaining private backend correlation data for diagnostics.
- Add evaluation fixtures covering common names, aliases, multilingual names,
  no-match creation, misleading fuzzy matches, and owner references.
- Run the refined ingestion UAT flow with:
  - one existing exact candidate;
  - multiple candidates requiring clarification;
  - explicit new-node creation;
  - existing-node memory and relationship updates;
  - first-person owner relationships.
- Add metrics for candidate count, clarification rate, attachment rate,
  new-node rate, rejected references, and lookup failures.
- Confirm that generic graph retrieval and unrelated semantic retrieval are
  unchanged.

**Exit criteria:** the interactive refined-ingestion trace demonstrates the
full flow reliably, the regression suite passes, and the feature can be
enabled without exposing hidden graph identifiers or allowing unsafe writes.

### Implementation Order Summary

```text
Wave 0  contracts and invariants
   -> Wave 1  run-scoped reference registry
   -> Wave 2  deterministic identity lookup
   -> Wave 3  bounded candidate context packets
   -> Wave 4  autonomous extractor resolution proposals
   -> Wave 5  clarification and update-agent handoff
   -> Wave 6  hardening, evaluation, and UAT
```

Each wave should land with focused unit and integration tests before the next
wave changes prompt behavior or write orchestration.

## Planner Output

The planner must continue to produce a normal candidate entity, with lookup metadata added where appropriate. It must not produce a graph query.

Conceptual example:

```json
{
  "local_ref": "CANDIDATE_PERSON_001",
  "entity_type": "Person",
  "display_name": "Marco",
  "aliases": [],
  "lookup": {
    "fields": ["display_name", "name", "normalized_name", "aliases"],
    "matching_policy": "deterministic_identity_candidates",
    "max_candidates": 5
  }
}
```

The backend owns:

- normalization rules;
- label restrictions;
- searchable field selection and ordering;
- candidate limits;
- exclusion rules;
- exact and fuzzy classification;
- graph query construction;
- related-context hydration.

The LLM cannot invent normalized values, persisted IDs, labels outside the graph taxonomy, or lookup parameters that bypass backend policy.

## Identity Lookup

For each planned entity, the backend creates an `EntityLookupRequest` containing at least:

- the planner's local candidate reference;
- the target graph label;
- the proposed display name and aliases;
- permitted identity fields;
- the matching policy;
- the maximum number of candidates.

For a Person candidate, the lookup normally considers:

- `display_name`;
- `name`;
- `normalized_name`;
- aliases;
- deterministic name tokens where a partial personal name is supplied.

The lookup must be label-constrained. A Person lookup must not accidentally return a Place, Organization, or other node with the same text.

The lookup result classifies the evidence without deciding the final LLM action:

| Status | Meaning |
| --- | --- |
| `no_candidates` | No existing node was found using the configured deterministic policy. |
| `one_candidate` | One existing node is a plausible deterministic candidate. |
| `multiple_candidates` | More than one existing node is plausible. |
| `fuzzy_candidates_only` | Similar results exist, but none qualifies for deterministic identity matching. |

Fuzzy or semantic results may be included as clearly marked hints, but they must never be presented as confirmed identity matches.

## Candidate Context Packet

The backend creates one packet per planned entity. It contains the lookup result and a bounded context item for each candidate.

Conceptual example:

```json
{
  "candidate_ref": "CANDIDATE_PERSON_001",
  "proposed_identity": {
    "label": "Person",
    "display_name": "Marco",
    "aliases": []
  },
  "lookup_status": "multiple_candidates",
  "candidates": [
    {
      "ref": "NODE_000001",
      "label": "Person",
      "display_name": "Marco Bianchi",
      "aliases": ["Marco"],
      "match_kind": "name_token",
      "related_context": {
        "relationship_summaries": ["university friend"],
        "relevant_memory_summaries": ["Attended university together"],
        "place_hints": ["Milan"]
      }
    },
    {
      "ref": "NODE_000002",
      "label": "Person",
      "display_name": "Marco Verdi",
      "aliases": ["Marco"],
      "match_kind": "name_token",
      "related_context": {}
    }
  ],
  "guidance": "Use an existing ref only when the source and context identify it sufficiently. Otherwise request clarification or create a new candidate."
}
```

Candidate context may include, subject to existing visibility and privacy policies:

- display name and permitted aliases;
- concise relationship summaries;
- relevant MemoryLog summaries;
- relevant places, organizations, or events;
- source evidence summaries when allowed;
- temporal hints useful for distinguishing candidates.

It must exclude:

- persisted graph IDs;
- unrestricted metadata and audit fields;
- unrelated private memories;
- raw database records;
- executable instructions embedded in stored user text.

Original user wording, when included as evidence, must be delimited and explicitly marked as data.

## LLM Resolution Outcomes

The extractor may produce one of the following structured outcomes for each planned entity:

### `CREATE_NEW`

Use when no suitable existing candidate is identified, or when the user explicitly clarifies that the entity is new.

```json
{
  "candidate_ref": "CANDIDATE_PERSON_001",
  "action": "CREATE_NEW",
  "reason": "No existing Marco matches the available evidence."
}
```

The backend allocates the persisted ID and applies the normal graph-write validation.

### `ATTACH_TO_EXISTING`

Use when the extractor can identify one supplied existing reference.

```json
{
  "candidate_ref": "CANDIDATE_PERSON_001",
  "action": "ATTACH_TO_EXISTING",
  "target_ref": "NODE_000001",
  "reason": "The user clarified that Marco is the university friend."
}
```

The existing node normally receives new MemoryLog, relationship, claim, or perception records. Selecting an existing node does not automatically mean that its Person properties should be mutated.

### `REQUEST_CLARIFICATION`

Use when the available evidence is insufficient to select one candidate or safely create a new entity.

The LLM asks a user-facing question using human-readable candidate summaries. It must not expose backend IDs or ask the user to choose an internal alias.

### `IGNORE_OR_DEFER`

Use when the reference is too weak, irrelevant, or outside the current extraction scope. This avoids forced node creation.

## Clarification Loop

When clarification is required:

1. The extractor returns a structured clarification request and does not create or bind the entity.
2. The application presents a natural-language question using candidate summaries.
3. The user's response is reintroduced with the original candidate, lookup packet, and clarification state.
4. The LLM chooses `CREATE_NEW`, `ATTACH_TO_EXISTING`, or another clarification request.
5. The backend revalidates the selected reference and refreshes the relevant node state before producing a write plan.

Example:

```text
Which Marco did you have dinner with: Marco Bianchi, Marco Verdi, or Marco Rossi?
```

After the user replies:

```text
Marco Bianchi, the person I attended university with.
```

the extractor may attach the event to the supplied existing reference and produce a relationship from `OWNER` to that node.

## Existing Node Updates

The default update behavior is additive and evidence-preserving:

- create a MemoryLog for the new event or fact;
- create or update the relevant relationship;
- create a Claim, Perception, or RelationshipContext when appropriate;
- preserve the original wording and provenance.

Direct property patches to an existing Person require a separate structured proposal and backend validation. They must not be used as an implicit consequence of fuzzy matching.

The phrase “update Marco” therefore normally means “attach new graph evidence to the resolved Marco node,” not “overwrite the Person node.”

## Reference Contract

The model-facing reference model is:

| Reference | Meaning |
| --- | --- |
| `OWNER` | Canonical owner node. This is the only model-facing owner identity. |
| `CANDIDATE_PERSON_001` | Entity proposed by the current planning/extraction run. |
| `NODE_000001` | Existing hydrated graph node in the current context packet. |
| `REL_000001` | Existing hydrated relationship, when exposed. |
| `MEMORY_000001` | Existing hydrated memory, when exposed. |

The exact numeric aliases are generated by a run-scoped reference registry. They are not persisted.

The backend maintains the private mapping:

```text
model_ref -> persisted_graph_id
```

All model-selected references must be validated against this registry. References not present in the packet are rejected or converted into a clarification/error path.

The current codebase contains more than one reference-format convention, including uppercase graph-context aliases and lowercase agentic refs. Before implementation, these conventions must be reconciled behind one registry and validator. The feature must not introduce a third independent alias system or expose raw IDs to the LLM.

## Owner Behavior

- `OWNER` is injected into relevant prompts as the canonical owner reference.
- First-person expressions such as “I”, “me”, and “my” resolve to `OWNER` when the language context supports that interpretation.
- A relationship such as “I had dinner with Marco” has `OWNER` as one endpoint and the resolved Marco node as the other.
- Ordinary Person lookup excludes the owner unless the source explicitly refers to the owner.
- The LLM cannot create or patch a Person with `is_owner=true`.
- The owner bootstrap service remains the only authority allowed to create or validate the owner node.

## Backend Responsibilities

Backend services must own:

- lookup request validation;
- deterministic graph search and candidate classification;
- related-context hydration and redaction;
- run-scoped alias allocation;
- alias-to-persisted-ID mapping;
- validation of LLM resolution outcomes;
- owner alias validation;
- conversion to graph write plans;
- final graph execution;
- revalidation after clarification.

LLM processes may own:

- interpreting the source text;
- deciding whether the supplied context is sufficient;
- selecting among supplied candidate references;
- requesting clarification;
- deciding whether the intended entity should remain new;
- proposing the graph effects justified by the source.

LLM processes may not:

- execute graph lookups;
- generate Cypher;
- invent graph IDs or aliases;
- select an unsupplied reference;
- silently merge two existing nodes;
- treat fuzzy evidence as confirmed identity;
- write directly to the graph.

## Relationship And Memory Behavior

Identity resolution is applied before relationship and memory-log extraction so that extracted objects can target the correct endpoint.

For example:

```text
I had dinner with Marco, the person I attended university with.
```

Expected behavior:

1. Plan a Person candidate for Marco.
2. Resolve the candidate against existing Person nodes.
3. Select the university-friend node if the evidence is sufficient.
4. Create a MemoryLog for the dinner.
5. Create or update the relationship from `OWNER` to the resolved Marco node.
6. Preserve the source evidence and provenance.

If identity remains ambiguous, steps 4 and 5 are blocked until clarification is obtained.

## Reuse Of Existing Resolution Logic

The current `ConservativeResolutionService` already performs late exact-match resolution. The planned implementation should extract its deterministic matching behavior into a reusable identity lookup service.

The same lookup result should be reused by:

- pre-extraction candidate context generation;
- clarification rendering;
- post-extraction resolution validation;
- final write-plan construction.

This prevents the pre-extraction packet and final executor from applying different matching rules.

## Failure And Safety Rules

- A failed lookup must not silently create a duplicate when the backend is unavailable or incomplete.
- A candidate packet with multiple matches must not be treated as a unique match.
- Fuzzy-only results must remain explicitly marked as uncertain.
- Missing or stale alias mappings must block the affected write proposal.
- A clarification response that cannot be mapped to a supplied candidate must produce another clarification or a new-node decision, never an inferred persisted ID.
- Context hydration failures should degrade to a smaller candidate packet or clarification, not to unrestricted retrieval.
- Owner references must remain scoped to the configured canonical owner.

## Functional Acceptance Criteria

The feature is complete when:

- every planned entity can receive a backend-generated lookup packet before extraction;
- lookup uses backend-owned deterministic graph queries;
- no LLM process generates Cypher or executes graph access;
- exact, ambiguous, fuzzy-only, and no-candidate outcomes are distinguishable;
- multiple candidates receive separate references and bounded context;
- the extractor can create, attach, defer, or request clarification through structured output;
- clarification responses can resolve to an existing supplied reference or a new entity;
- existing-node updates create appropriately linked memories or relationships without implicit Person overwrites;
- all model-facing references resolve through one run-scoped registry;
- raw graph IDs are absent from model-facing packets;
- `OWNER` remains the only model-facing owner reference;
- first-person relationships resolve to `OWNER`;
- invalid, invented, stale, or cross-graph references cannot reach graph execution;
- the existing ingestion behavior remains unchanged when identity lookup is not relevant.

## Focused Tests

Tests should cover:

- deterministic matching by display name, name, normalized name, and aliases;
- partial personal-name lookup such as `Marco` returning all relevant candidates;
- label-constrained lookup;
- one candidate, multiple candidates, fuzzy-only, and no-candidate packets;
- bounded context hydration and omission of raw graph IDs;
- stable alias reuse within one ingestion run;
- rejection of invented or unsupplied references;
- clarification followed by existing-node attachment;
- clarification followed by new-node creation;
- creation of a MemoryLog and relationship for an attached existing node;
- prevention of implicit Person property overwrites;
- first-person references resolving to `OWNER`;
- ordinary Person lookup not accidentally selecting the owner;
- revalidation after clarification or concurrent graph changes;
- unchanged behavior for unrelated ingestion flows.

## Out Of Scope

This feature does not define:

- a new personality taxonomy;
- automatic personality inference or profile approval;
- global semantic retrieval policy;
- unrestricted graph neighborhood retrieval;
- automatic merging of duplicate graph nodes;
- a user-facing graph-editing language;
- LLM-generated Cypher;
- cross-run stability of model-facing aliases.
