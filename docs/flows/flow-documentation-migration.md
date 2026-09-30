# Flow documentation migration plan

## Status

Transitional migration plan. This file is a working checklist, not target
architecture or implementation authority. Delete it after every listed
transaction is complete, the `flows` README indexes only current documents, and
inbound links have been verified.

## Goal

Retain functional behavior that users and future application states need to
understand, while moving AI-runtime, prompt, toolbox, DTO, reference, and
backend implementation details to their existing canonical owners. The target
`flows` folder describes what the product does; it does not compete with
`ai-engineering`, `architecture`, or `network` as a technical source of truth.

## Migration rules

- Move a concept only when it remains valid in the clean-slate architecture.
- Do not preserve a legacy name, state, ID family, action-plan abstraction, or
  compatibility behavior merely as historical context.
- A functional flow links to its technical contract instead of reproducing it.
- A prompt template implements a documented state convention; it is not the
  only statement of the state’s behavioral purpose.
- New state DTOs are purpose-specific. Do not recreate an all-purpose
  ingestion-object catalogue.
- Delete a source only after its retained concepts have a canonical owner and
  all inbound documentation links are updated.

## Destination map

| Current source | Keep as current flow | Move to canonical owner | Retire |
| --- | --- | --- | --- |
| `ingestion.md` | User-visible source-to-confirmed-memory behavior, interruption expectations, idempotency, and uncertainty handling. | State sequencing to deterministic workflows; state behavior to application-state conventions; context/ref/tool protocol to AI engineering; MemoryLog behavior to network. | Waves, old pending-process routing, `GraphContextPack`, generic plans, static tool names, raw reference families, backend state catalogues. |
| `entity-resolution.md` | Homonyms, incomplete identity, event/place ambiguity, evidence, explicit merge/split expectations, and clarification usefulness. | Ref rendering and owner projection to context docs; node-state LLM behavior to state conventions. | Automatic resolution engine, static aliases, automatic duplicate collapse, rigid resolved-map pipeline details. |
| `interrogation.md` | Natural-language questions, structured query, graph navigation, grounding, timeline/map behavior, and answer limits. | Query state/runtime to application states; retrieval mechanics to vector retrieval; UI behavior to UI requirements. | Provider-call, prompt, and toolbox mechanics. |
| `memory-management-agent.md` | Future maintenance product behavior. | Rename and move to functional requirements as `memory-maintenance-and-corrections.md`; future state behavior later belongs in application-state conventions. | The current agent/toolbox contract, static tool list, and premature implementation detail. |
| `structured-ingestion-objects.md` | None as a standalone catalogue. | Proposal-versus-persisted-record boundary to AI contracts; source/media provenance to domain/integration docs; MemoryLog to network; state-specific DTOs to state conventions. | Generic candidate graph, generic extraction/action/write plans, old ref vocabulary, and deprecated staged-pipeline DTOs. |

## Wave 1 — State-convention source of truth

Create `docs/ai-engineering/application-states/ingestion/` with a README and
one document for each current ingestion state:

```text
ingestion reasoning
node candidate
node resolution/write
memory/context write
relationship write
```

Each state document defines its purpose, why it exists, required context,
reference rendering level, allowed tools, decision boundaries, expected typed
result, clarification behavior, compact handoff, and prompt-template link. It
does not duplicate a full prompt body or provider transcript mechanics.

**Exit condition:** the deterministic workflow and every retained ingestion
flow can point to state conventions rather than explain internal LLM behavior.

## Wave 2 — Rewrite current functional flows

### Ingestion

Rewrite `ingestion.md` as a concise index around:

```text
source or derived transcript
  -> bounded context preparation
  -> phased ingestion workflow
  -> confirmed graph outcome or clarification
  -> user-facing final response
```

Keep only functional expectations and direct links to workflow, state
conventions, clarification requirements, entity resolution, MemoryLog, and
source/media handling.

### Entity resolution

Retain functional outcomes: reuse a supplied existing object, create a new
object, ask clarification, defer, or later propose a user-confirmed merge.
Describe backend lookup as bounded evidence and the LLM state as the semantic
decision-maker within typed contracts. Preserve examples for similarly named
people, incomplete places, and repeated events.

### Interrogation

Retain query behavior and graph/UI handoff. Link to `MemoryQueryState`, vector
retrieval, context packages, and UI requirements. Remove provider and runtime
mechanics.

**Exit condition:** the three retained flow documents have no duplicated AI
runtime design, deprecated IDs, plan terminology, or stale pending-process
mechanics.

## Wave 3 — Preserve future memory maintenance clearly

Create `docs/requirements/functional/memory-maintenance-and-corrections.md`.
It documents future product behavior without claiming that a maintenance agent
or its tools are implemented in MVP.

Keep these future capabilities:

- user-proposed correction with evidence and explicit confirmation where a
  change is destructive;
- contradiction review that distinguishes a conflict from a valid temporal
  update or nuance;
- user-confirmed duplicate merge and erroneous-merge split;
- lifecycle changes such as confirm, dispute, archive, expire, or delete;
- contact/evidence updates and metadata promotion with provenance.

The document must include functional examples such as:

```text
Correction: "Luca's current number is Y, not X."
Expected behavior: retain the earlier value with provenance, propose Y as the
current value, and request confirmation only if the update is consequential.

Possible conflict: a new memory places an apparently identical dinner in Milan,
while the prior memory says Turin.
Expected behavior: ask whether these are distinct events only if available time,
participants, and evidence cannot preserve both safely.

Duplicate review: two records appear to describe the same Marco.
Expected behavior: show the user the meaningful distinguishing evidence and
require confirmation before a merge; never silently merge identities.
```

It links to memory lifecycle, temporal model, entity resolution, clarification
UX, and future application-state conventions. It contains no provider tool
names, implementation status model, or generic toolbox declaration.

**Exit condition:** delete `memory-management-agent.md` after its functional
content and examples have moved.

## Wave 4 — Decompose and delete ingestion-object catalogue

Migrate only these high-level concepts from `structured-ingestion-objects.md`:

- model-facing semantic proposal versus backend-enriched persistent record;
- purpose-specific DTOs with descriptions and no backend-owned identifiers in
  LLM outputs;
- source/transcript provenance survives all writes;
- validated typed graph mutation commands, never raw model text;
- `MemoryLog` remains a source-backed additive atom.

Canonical destinations:

| Concept | Destination |
| --- | --- |
| Proposal/persisted record boundary and DTO guidance | `ai-engineering/contracts/` |
| State input/output DTO ownership | State-convention documents in `ai-engineering/application-states/ingestion/` |
| Context, refs, and rendering | `ai-engineering/context-and-prompts/` |
| Reasoning/planning preparation | `ai-engineering/runtime/agentic-state-preparation.md` |
| Source/media provenance | `network/`, `external-integrations/media-ingestion.md` |
| MemoryLog semantics | `network/memory-log-model.md` |

Delete rather than migrate `CandidateMemoryGraph`, `ExtractionPlan`,
`ExtractionTask`, `MissingEntityRequiredDraft`, generic `GraphWritePlan`, old
candidate/ref families, and the broad candidate-object inventory. Concrete
state DTOs will be introduced only when their state is implemented.

**Exit condition:** delete `structured-ingestion-objects.md` and its inbound
links.

## Wave 5 — Final folder cleanup

- Update `docs/flows/README.md` to index only `ingestion.md`,
  `entity-resolution.md`, and `interrogation.md`.
- Remove this transitional plan and its migration ledger.
- Verify no source references remain in documentation or code.
- Keep future maintenance requirements under `requirements/functional/`, not
  under `flows/` until a concrete user workflow is approved.

## Explicit non-goals

- Do not implement any runtime behavior in this documentation migration.
- Do not define a generic maintenance agent or its tool list before selecting
  the future state(s) that need it.
- Do not reintroduce deprecated plan/action objects to retain historical detail.
- Do not convert future maintenance concepts into MVP commitments.
