# Ingestion Identity Resolution And Context Packets

## Status

Design agreed for implementation. This document captures the behavior discussed for resolving planned entities against existing graph nodes before extraction and write planning.

## Locked Decisions

- Use a generic identity-resolution service, initially enabled for identity-
  rich labels such as `Person`, `Organization`, and `Place`.
- Derive lookup fields and matching policy in backend code from the planned
  candidate. The planner does not control graph-search policy.
- Use deterministic normalized name, name-token, and alias matching to find
  candidates. Fuzzy or semantic results remain explicitly labeled as weaker
  evidence and are never backend bindings.
- Use one run-scoped reference registry. Existing ingestion-context nodes use
  the canonical `NODE_000001`-style reference family; proposed entities use
  `CANDIDATE_*`; the owner uses `OWNER`.
- Resolution behavior is prompt-guided and LLM-decided. The backend classifies
  evidence and enforces safety, but it does not deterministically choose the
  final extractor action. Lookup status is context, not a decision rule.
- The LLM drives semantic planning, extraction, and resolution proposals from
  the context supplied by the backend. The backend drives graph lookup,
  reference translation, validation, deterministic write planning, and graph
  execution.
- Backend validation errors must be explicit, structured, and sufficiently
  detailed for the LLM to correct its proposal. The backend must not hide an
  invalid proposal behind an automatic create, attach, or other fallback.
- Candidate and context limits are configurable. Initial provisional values
  are defined in the Wave 3 section and may be tuned during implementation.
- Clarifications belong to the current session. Questions and answers are
  normal history messages injected into later pipeline contexts.
- Contracts will be extended for lookup packets, resolution proposals,
  session clarification context, and run-scoped references.
- The feature will be integrated directly into the relevant ingestion path;
  no separate production rollout phase is planned.

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

1. **Lookup is backend-owned.** The backend creates a structured lookup request from the planned candidate. The LLM never produces Cypher or an executable graph query.
2. **Planning and identity resolution are separate.** The planner describes the entity through normal candidate fields. The backend derives lookup fields and performs lookup before extraction.
3. **Lookup is deterministic; resolution is not.** Name and alias lookup may return candidates using deterministic normalization and bounded matching. The resulting status and match kind are evidence supplied to the LLM; they do not automatically bind, create, reject, or clarify an entity.
4. **The extractor is autonomous within explicit boundaries.** It may select an existing candidate, request clarification, or keep the entity as new when the packet supports that decision.
5. **Graph execution remains backend-owned.** An LLM decision is a proposal. The backend validates its structure, references, scope, labels, and protected-field rules, reports actionable errors, and converts valid proposals into an authorized write plan. It does not replace a failed proposal with a hidden fallback.
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
  -> entity extraction
  -> LLM resolution proposal
  -> backend proposal validation and reference compilation
  -> memory and relationship planning/extraction
  -> graph write planning
  -> backend execution
```

The existing broad whole-source retrieval remains useful for general reasoning. It is not a replacement for per-candidate identity lookup. The new stage gives every planned node proposal a deterministic lookup result and a focused context packet.

## Multi-Wave Implementation Plan

The implementation is intentionally split into independent waves. Each wave
is a bounded implementation slice. The feature is intended to be integrated
directly into the relevant ingestion path; the waves are sequencing and test
boundaries, not a deferred rollout or parallel production implementation.

### Wave 0: Feature Foundation And Local Code Quality

**Scope:** define and test the identity-resolution contracts and integration
boundaries without refactoring the repository wholesale or changing runtime
LLM behavior.

Repository-wide code-quality principles are documented in the technical
principles. In this wave, the quality gate applies to new and edited feature
code. Existing large or uncertain modules are not refactored unless the
feature cannot be integrated safely without doing so.

#### Integration Boundary

Identify the smallest existing integration points for:

- planned candidate entities;
- graph context rendering;
- existing resolution;
- extraction context construction;
- clarification/session history;
- final write-plan validation.

Keep orchestration changes limited to dependency wiring. Place new contract,
lookup-packet, reference, and validation behavior in focused modules below
500 lines, with approximately 450 lines as the preferred working target.

#### Feature Contracts

Add typed contracts for:

- `EntityLookupRequest`;
- `EntityLookupCandidate`;
- `EntityLookupResult`;
- `EntityLookupContextPacket`;
- `EntityResolutionProposal`;
- session-scoped clarification context;
- run-scoped reference registry entries.

The contracts must enforce:

- lookup requests are derived by backend code from normal candidate fields;
- planner output contains no graph query or LLM-controlled search policy;
- lookup statuses distinguish no candidate, one candidate, multiple
  candidates, and fuzzy-only candidates;
- resolution actions are `CREATE_NEW`, `ATTACH_TO_EXISTING`,
  `REQUEST_CLARIFICATION`, and `IGNORE_OR_DEFER`;
- `target_ref` is required only for existing-node attachment;
- clarification questions and answers remain normal session-history messages;
- no new graph taxonomy object or separate clarification subsystem exists.

#### Reference And Owner Invariants

Define and test the reference mapping contract:

```text
model reference -> persisted graph ID
persisted graph ID -> model reference
```

Use the agreed model-facing families:

```text
OWNER
CANDIDATE_PERSON_001
NODE_000001
REL_000001
MEMORY_000001
```

The full registry implementation belongs to Wave 1. Wave 0 locks the
contract for:

- existing versus proposed status;
- object kind and label;
- graph and session scope;
- reference reuse within one run;
- rejection of invented, stale, cross-run, and cross-graph references;
- `OWNER` resolution only through the owner manager.

Model-facing projections must exclude persisted graph IDs, unrestricted graph
properties, and backend metadata.

#### Prompt-Safety Boundary

Wave 0 does not change production prompts. It defines the boundary later
prompts must follow:

- the LLM never generates Cypher;
- the LLM never receives persisted graph IDs;
- the LLM selects only references supplied in its context;
- fuzzy results are never represented as confirmed identity;
- owner references use `OWNER`;
- backend validation remains mandatory after every LLM proposal.

#### Local Code Quality

For new or edited feature code:

- keep modules below 500 lines;
- use one primary responsibility per module;
- avoid new compatibility wrappers, deprecated aliases, duplicate services,
  and hidden fallbacks;
- remove directly related dead code only when its obsolescence is clear;
- do not perform broad unrelated cleanup;
- do not grow an existing monolith when a focused module can own the feature.

#### Tests And Fixtures

Add focused tests for:

- lookup request construction from candidate fields;
- lookup status validation;
- resolution action and target validation;
- existing versus proposed references;
- owner alias protection;
- invalid and invented reference rejection;
- session-history clarification context;
- persisted-ID exclusion from model-facing payloads;
- contract serialization and deserialization.

Add boundary tests proving the current planner contract and unrelated
ingestion behavior remain compatible. Existing resolution behavior must remain
unchanged until Wave 2.

#### Wave 0 Exit Criteria

Wave 0 is complete when:

- global technical principles document the repository-wide coding philosophy;
- this feature document reflects the local cleanup boundary;
- integration points are identified;
- all feature contracts are exported and tested;
- reference and owner invariants are covered;
- new and edited feature modules remain below 500 lines;
- no new legacy, deprecated, duplicate, or hidden fallback path is added;
- uncertain unrelated legacy code remains untouched;
- existing tests and refined-ingestion UAT checks pass.

### Wave 1: Canonical Reference Registry

**Scope:** establish one backend-owned reference registry for the ingestion
run. This wave makes the mapping between application identities and
LLM-facing aliases explicit and reusable before lookup results are added to
prompts.

#### Locked Identity Model

The persisted application ID is the source of truth. In normal operation this
is a UUID, but the registry must accept the current graph's opaque internal
IDs as well, including configured owner IDs and relationship identifiers. The
internal ID is never a model-facing identity and is never emitted in a
context packet.

The backend creates an alias when an existing object is injected into an LLM
context. The LLM does not allocate aliases and does not control the registry.
The backend maintains both directions of the mapping:

```text
model alias       -> internal application ID
internal ID       -> model alias
```

The canonical graph-facing alias families are uppercase:

```text
OWNER
NODE_000001
REL_000001
MEMORY_000001
CONTEXT_000001
MEDIA_000001
CANDIDATE_PERSON_001
```

`OWNER` is reserved and is resolved only through the owner manager. Numeric
aliases use fixed-width, six-digit counters for persisted graph objects. A
candidate reference uses the candidate's model-facing kind and remains
unbound until a backend resolution or creation operation supplies an internal
ID.

The distinction is important:

```text
OWNER              -> 7f...                    existing owner
NODE_000001        -> 3a...                    existing Marco Bianchi
NODE_000002        -> 91...                    existing Marco Verdi
CANDIDATE_PERSON_001 -> no internal ID yet      planned Marco
```

After the extractor selects `NODE_000001`, the executor resolves that alias
to the internal ID. If it selects `CREATE_NEW`, the backend creates the node,
binds `CANDIDATE_PERSON_001` to the new internal ID, and may allocate a
`NODE_000003` alias only when that node is later exposed as an existing object
in the same run. The candidate reference is not silently rewritten in the
LLM payload.

#### Registry Contract

Add one focused `RunReferenceRegistry` service/module below 500 lines. It is
created for one graph and one ingestion run, and its public operations are:

- register an existing object with its internal ID, object kind, label, and
  optional display metadata, returning a stable uppercase alias;
- register the canonical owner as `OWNER` through the owner manager;
- register a proposed candidate with `CANDIDATE_*` status and no internal ID;
- bind a proposed candidate to an internal ID after backend resolution or
  graph creation;
- resolve a supplied alias to an internal ID for validation and execution;
- resolve an existing internal ID to its already allocated alias;
- export a backend-only snapshot and a separate model-facing projection.

Registration is first-seen deterministic within a run. Registering the same
internal ID and object kind reuses the same alias across entity, memory,
relationship, candidate, and clarification packets. Registering the same ID
as incompatible kinds, allocating a reserved alias, or binding two different
IDs to one alias is a validation error.

Every registry entry records:

- graph scope and run/session scope;
- object kind and existing/proposed status;
- model-facing alias;
- internal ID for existing or bound entries, backend-only;
- owner status where applicable.

The registry rejects unknown, invented, stale, cross-run, and cross-graph
references. `OWNER` cannot be registered as a normal node, rebound to a
candidate, or resolved from an LLM-supplied internal ID. A candidate may be
bound only by backend code after the resolution proposal has passed
validation.

#### Integration Changes

- Generalize the existing low-level ID alias mapper so it can map opaque
  internal strings in addition to UUIDs. Preserve its uppercase allocation
  and reverse-lookup behavior rather than introducing a second generic mapper.
- Replace the custom alias counter and raw-ID passthrough in the ingestion
  graph-context pack builder with `RunReferenceRegistry`.
- Make the graph-context package builder and ingestion context package use the
  same registry instance or serialized registry snapshot for a run. The same
  graph object must never receive one alias in broad context and another alias
  in candidate or clarification context.
- Migrate write-plan validation and execution to resolve references through
  the registry. If `alias_map` remains in a compatibility contract during the
  migration, it is a read-only projection derived from the registry and not a
  second source of truth.
- Carry the backend registry snapshot through the existing run/session state
  used by clarification history. Do not introduce a new graph taxonomy node
  or a separate clarification store.
- Ensure all model-facing graph packets contain uppercase canonical aliases
  and contain no persisted IDs, registry scope fields, or unrestricted graph
  metadata.
- Keep generic agent-local references outside ingestion isolated. They must
  not leak into graph-facing ingestion packets or create a second alias for
  an object already registered in this run. Any boundary conversion must be
  explicit and one-way.

Orchestration changes to large existing modules are limited to constructing,
passing, or restoring the registry. Allocation, validation, serialization,
and reference handling belong in focused feature modules.

#### Registry Lifecycle

1. Start an ingestion run with an empty registry scoped to the current graph
   and run ID.
2. Register the owner through the owner manager as `OWNER`.
3. Register hydrated graph objects as they are rendered into context.
4. Register planned entities as unbound `CANDIDATE_*` entries.
5. Reuse the registry while lookup, extraction, clarification, planning, and
   validation produce packets for the same run.
6. Bind candidates only after backend validation and graph creation or
   attachment.
7. Persist only the resulting graph IDs and approved write data. The
   model-facing aliases are run-scoped and are not written to the graph as
   identity.

#### Tests

Add focused tests for:

- uppercase alias allocation and fixed-width formatting;
- stable alias reuse for the same internal ID;
- reverse resolution from alias to internal ID;
- UUID, owner, and composite/opaque internal ID handling;
- reserved `OWNER` registration and owner-manager-only resolution;
- existing versus proposed entries and candidate binding;
- object-kind and alias-collision validation;
- rejection of invented, stale, cross-run, and cross-graph references;
- registry snapshot round-trip across clarification/session boundaries;
- persisted-ID exclusion from every model-facing projection;
- consistent relationship endpoint aliases across all context packets;
- graph-context builders delegating to the registry rather than allocating
  aliases independently;
- write-plan and executor resolution through the registry;
- no lowercase graph aliases leaking from generic agentic contexts.

Existing unrelated agentic reference tests may remain lowercase if those
references are local to that protocol. Tests for graph-facing ingestion
packets must use the canonical uppercase families above.

#### Exit Criteria

Wave 1 is complete when:

- one backend registry is the source of truth for all graph-facing aliases in
  an ingestion run;
- internal IDs remain available only to backend validation and execution;
- `OWNER` resolves only through the canonical owner manager;
- existing objects, proposed candidates, and relationships have explicit
  lifecycle/status semantics;
- aliases are uppercase, stable within a run, and reused across packets;
- the custom ingestion alias counter and independent alias allocation paths
  are removed;
- compatibility maps, if still present, are derived registry projections;
- model-facing packets contain no persisted IDs or hidden backend metadata;
- no unrelated repository-wide refactor or prompt behavior is introduced.

### Wave 2: Deterministic Identity Lookup

**Scope:** backend lookup service and extraction-stage integration point. Lookup
runs after entity planning and before entity extraction. No new LLM decision
behavior is introduced in this wave; the extractor only receives the bounded
lookup packet as additional context.

**Deliverables:**

- Add a focused deterministic identity lookup service that consumes
  `PlannedEntityRefDraft` values and returns an
  `EntityLookupContextPacket` for each typed planned entity.
- Derive `EntityLookupRequest` in backend code from `mention_text`, aliases,
  the suggested entity type, and typed identity fields when those fields exist.
  The request must not contain an LLM-generated graph query or search policy.
- Extract shared exact-identity matching helpers so the existing
  `ConservativeResolutionService` and the new pre-extraction lookup do not
  implement different normalization rules. Existing downstream resolution
  remains exact-only until later waves change its behavior explicitly.
- Implement label-constrained deterministic lookup for identity fields:
  - display name;
  - name;
  - normalized name;
  - aliases;
  - one-token partial names such as `Marco` matching `Marco Bianchi`.
- Use the Wave 1 registry when candidates are returned. Existing candidates
  receive `NODE_000001`-style references reused across later packets.
- Classify results as `no_candidates`, `one_candidate`,
  `multiple_candidates`, or `fuzzy_candidates_only`.
- Keep fuzzy retrieval optional and explicitly non-binding. It is used only
  when a graph service exposes an explicit fuzzy lookup operation; broad text
  search results are never relabeled as fuzzy identity matches.
- Exclude the canonical owner from ordinary Person lookup. Direct first-person
  interpretation belongs to the Wave 4 prompt boundary; Wave 2 only preserves
  an already supplied `OWNER` reference.
- Carry lookup packets into `IngestionContextPackage` and extraction prompt
  payloads without exposing registry snapshots or persisted graph IDs.
- Apply active-lifecycle filtering and fail the ingestion stage when the
  backend lookup fails. A lookup failure must never silently become
  `CREATE_NEW`.

#### Deterministic Matching Rules

- Normalize case and whitespace before comparison.
- Exact display/name/normalized-name matches outrank exact alias matches.
- Exact aliases on an existing node match a proposed display mention as an
  alias match.
- Token matching is restricted to name fields and is only used for a single
  requested token. Descriptions, memory text, and arbitrary properties are
  not identity fields.
- Multiple graph nodes with the same matching name remain separate
  candidates. No automatic deduplication or conflict resolution is performed.
- Exact and token candidates take precedence over fuzzy candidates. Fuzzy
  candidates are returned only when no deterministic candidate exists.

#### Initial Configuration

`identity_lookup_max_candidates` is configurable through
`IDENTITY_LOOKUP_MAX_CANDIDATES` and defaults to `5`. The backend may query a
larger bounded result window to avoid truncating deterministic matches before
filtering, but the model-facing packet never contains more than this limit.

**Tests:**

- `Marco` returns all relevant Marco candidates;
- full names and aliases match correctly;
- planned entity fields produce the expected backend lookup request;
- unrelated labels are excluded;
- one, multiple, fuzzy-only, and empty results are classified correctly;
- owner exclusion and preservation of `OWNER` references;
- lifecycle filtering and registry alias reuse;
- lookup packets contain no persisted graph IDs;
- backend failure does not silently trigger duplicate creation.

**Exit criteria:** every typed planned entity reaches a deterministic,
owner-filtered lookup before extraction in the production ingestion path; the
result is registry-backed and bounded; lookup failures stop the stage rather
than creating duplicates; no LLM-generated Cypher or graph mutation is
introduced.

### Wave 3: Bounded Candidate Context Packets

**Scope:** candidate hydration, redaction, packet rendering, and focused
extractor context delivery. The extractor still follows the existing output
behavior until Wave 4.

**Deliverables:**

- Hydrate a bounded context packet for each lookup candidate.
- Include only relevant context, such as:
  - permitted names and aliases;
  - concise relationship summaries;
  - relevant MemoryLog summaries;
  - place, organization, event, and temporal hints;
  - permitted source evidence.
- Use deterministic one-hop graph context and directly connected MemoryLogs.
  Semantic neighborhood expansion remains outside Wave 3.
- Apply existing lifecycle, visibility, privacy, and owner-scope policies.
  Archived, deleted, merged, hidden, and local-only records are excluded.
- Make candidate, related-object, and text limits configurable.
- Preserve exact, token, and fuzzy evidence explicitly; semantic identity
  evidence remains outside this wave.
- Delimit original user wording and mark it as user data, not instructions.
- Render related nodes, relationships, and MemoryLogs through the shared run
  registry. Only `OWNER` and generated model references are model-facing.
- Deliver packets only to extractors whose target or required context refs
  intersect the packet. Generic graph contexts remain unchanged.
- Continue sending only the minimal owner snapshot in generic contexts.

Wave 3 is read-only. It does not choose `CREATE_NEW`,
`ATTACH_TO_EXISTING`, or clarification actions; those decisions belong to
Wave 4. Fuzzy evidence remains explicitly non-binding and context hydration
must not promote it to confirmed identity.

**Tests:**

- three Marco candidates receive separate references and separate context;
- raw graph IDs and backend metadata are absent;
- unrelated neighbors are omitted;
- context limits are enforced;
- hidden or disallowed evidence is excluded;
- the same candidate reference is preserved across all packets;
- related nodes, relationships, and MemoryLogs reuse the run registry;
- owner relationship endpoints render as `OWNER`;
- extraction prompts receive only task-relevant packets;
- original wording is delimited as user evidence.

**Initial configurable limits:**

These are provisional implementation defaults and should remain configuration
values so they can be tuned during implementation and UAT:

| Setting | Initial value | Scope |
| --- | ---: | --- |
| `identity_lookup_max_candidates` | `5` | Maximum existing candidates per planned entity. |
| `identity_context_max_relationships` | `3` | Relationship summaries per candidate. |
| `identity_context_max_memory_logs` | `3` | Relevant MemoryLog summaries per candidate. |
| `identity_context_max_summary_chars` | `500` | Maximum characters per context summary. |
| `identity_context_max_total_chars` | `6000` | Maximum rendered candidate-packet size. |

The settings are exposed as `IDENTITY_CONTEXT_*` environment variables. The
final defaults should be confirmed against actual prompt sizes, provider
limits, privacy review, and refined-ingestion UAT results.

**Exit criteria:** the extractor can receive a safe, bounded overview of
possible existing nodes without receiving direct database identity data.

### Wave 4: LLM-Driven Resolution Proposals

**Scope:** context-first prompting, LLM resolution proposals, proposal
validation, reference compilation, and error feedback. The LLM makes the
semantic choice. The backend only determines whether the proposal is
structurally valid, safe to execute, and expressible as a graph write.
Wave 4 does not require a second independent resolver model call: the
resolution guidance may be appended to the existing agent prompt and use a
separate structured proposal/tool contract.

**Deliverables:**

- Keep the planner responsible for describing candidate identity through its
  normal candidate fields. The backend derives lookup fields and policy from
  those fields; the planner does not emit lookup instructions or queries.
- Add the candidate packet to every LLM process that can create or reference
  graph nodes, with the packet scoped to the current task.
- Add an LLM-facing resolution proposal output with the allowed outcomes:
  - `CREATE_NEW`;
  - `ATTACH_TO_EXISTING`;
  - `REQUEST_CLARIFICATION`;
  - `IGNORE_OR_DEFER`.
- Require the LLM to use only references supplied in its current packet. An
  existing-node target must be a supplied model-facing alias; the LLM never
  receives or generates a persisted graph ID.
- Instruct the LLM to use the full packet, source evidence, and session
  history to decide whether to attach, create, clarify, or defer. The lookup
  status does not select the action.
- Explain that exact, token, and fuzzy match kinds have different evidentiary
  strength without turning them into deterministic backend outcomes.
- Allow the LLM to select a fuzzy candidate when the complete context
  supports that decision; ask for clarification when the context is not
  sufficient.
- Make clarification an agent tool invocation rather than a free-form field
  on a resolution proposal. The tool owns the user-facing question and keeps
  the candidate and evidence references in session state.
- Append the resolution guidance only when the backend lookup packet contains
  one or more contextual matches. When there are no matches, keep the normal
  candidate prompt free of an unnecessary match-resolution block.
- Include a few behavioral examples in the match-resolution guidance. The
  examples demonstrate context-sensitive reasoning and are not deterministic
  rules or a scenario-to-action matrix.
- Prevent direct Person-property mutation as an implicit result of identity
  matching.
- Compile validated model-facing proposals into the existing backend
  `ResolutionResult` and `ResolvedEntityMap` without performing a second
  semantic identity search.
- Add backend validation that rejects invented or stale aliases, cross-run or
  cross-graph references, invalid labels, owner impersonation, protected
  field mutation, and unsupported actions.
- Return verbose structured validation errors to the LLM-facing process. Do
  not silently convert invalid output into `CREATE_NEW`,
  `ATTACH_TO_EXISTING`, or any other fallback.

When matches exist, the appended guidance should teach patterns such as:

- attach when surrounding context identifies one supplied candidate;
- ask the `ask_clarification` tool when the candidates remain
  indistinguishable;
- create a new node when the source explicitly distinguishes a new entity,
  even if a similarly named node exists;
- add a memory or relationship update when the source adds information about
  an existing entity rather than redefining its identity;
- use `OWNER` for first-person references and never create a second owner.

These are behavioral examples for the LLM, not backend decisions. The LLM may
choose a different valid action when the complete context supports it.

The backend classifies lookup evidence and enforces structural and graph
safety constraints. It does not choose a semantic outcome from the lookup
status. The LLM uses the prompt instructions, source evidence, session
history, and supplied candidate context to make that decision.

**Tests:**

- no-candidate, one-candidate, multiple-candidate, and fuzzy packets are all
  passed to the LLM as evidence without backend action selection;
- the LLM can propose create, attach, clarify, or defer for each evidence
  shape, and the backend compiles the selected proposal;
- ambiguous context can produce clarification, while informative context can
  support attachment or new-node creation;
- valid proposals referencing supplied fuzzy candidates are not rejected only
  because their match kind is fuzzy;
- invalid, invented, stale, cross-scope, or persisted-ID references are
  rejected with actionable errors;
- owner relationships use `OWNER` as the endpoint;
- invalid proposals do not silently fall back to another action;
- unrelated extraction flows retain their current behavior.

**Exit criteria:** the LLM can choose a resolution outcome from a bounded
context packet, and the backend can validate, explain, compile, and execute
that proposal without making a hidden semantic decision or performing a
second identity search.

### Wave 5: Clarification And Update-Agent Handoff

**Scope:** user clarification lifecycle and handoff from extraction to graph
update planning.

The agent must have a phase-appropriate toolbox. These tools are typed action
requests routed through backend validation and deterministic execution; they
are not unrestricted graph access.

**Deliverables:**

- Keep clarification state in the current session as conversation history.
  The history must retain and make available to later pipeline steps:
  - the original candidate;
  - the candidate packet;
  - the proposed graph effects;
  - the clarification question;
  - the user's answer and supporting evidence;
  - the owner and graph scope.
- Render human-readable clarification questions without exposing internal
  references or persisted IDs.
- Re-enter the pipeline with the original candidate, the user's answer, and
  the shared session history injected into the relevant prompts.
- Provide the relevant agent steps with tools for:
  - `ask_clarification`;
  - creating and updating nodes;
  - creating and updating MemoryLogs or other memory records;
  - creating and updating relationships or relationship contexts;
  - deferring or ignoring an action when appropriate.
- Scope tool availability by pipeline step. A planner may prepare candidate
  actions, while an update-capable agent may request node, memory, or
  relationship effects.
- Keep tool requests proposal-shaped. The backend validates references,
  ownership, protected fields, provenance, and graph scope before execution.
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
interactive ingestion validation after direct integration.

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
- Remove temporary compatibility paths that would allow the old late-only
  resolution behavior to bypass the new pre-extraction packet when the
  feature's relevant ingestion process is active.

**Exit criteria:** the interactive refined-ingestion trace demonstrates the
full flow reliably, the regression suite passes, and direct integration does
not expose hidden graph identifiers or allow unsafe writes.

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
wave changes prompt behavior or write orchestration. No separate production
rollout phase is required for the current scope.

## Planner Output

The planner must continue to produce a normal candidate entity. The backend
derives lookup requests from the candidate fields. The planner must not
produce lookup metadata that changes backend search policy and must not
produce a graph query.

Conceptual example:

```json
{
  "local_ref": "CANDIDATE_PERSON_001",
  "entity_type": "Person",
  "display_name": "Marco",
  "aliases": []
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
3. The question and the user's response become session history messages and
   are reintroduced with the original candidate and lookup packet.
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
