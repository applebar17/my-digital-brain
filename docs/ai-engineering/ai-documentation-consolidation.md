# AI engineering documentation consolidation

**Status:** transitional plan. Delete this file when the broad duplicate
sources have been retired and all indexes and references are current.

## Goal

Make `docs/ai-engineering/` a navigable set of single-purpose sources of truth.
The parent README is an index, not a second runtime handbook. Each technical or
functional rule is defined once in the file that owns it; other documents link
to that owner.

## Target structure

```text
docs/ai-engineering/
  README.md                         # section index only
  foundations/README.md
  contracts/README.md
  contracts/dto-first-contracts.md
  contracts/tool-definition-and-toolbox.md
  runtime/README.md
  runtime/agentic-state-framework.md
  runtime/agentic-history-session.md
  runtime/agentic-state-preparation.md
  runtime/tool-calling-protocol.md
  application-states/README.md
  providers/README.md
  context-and-prompts/README.md
  observability-and-evaluation/README.md
  migration/README.md
```

Existing focused documents remain in their current folders. This migration
does not add a new broad principles document.

## Canonical ownership map

| Rule or topic in the broad sources | One canonical owner | Consolidation action |
| --- | --- | --- |
| DTO-first proposals, backend-owned identifiers/provenance, explicit write commands, validation and recoverable model repair | [DTO-first contracts](contracts/dto-first-contracts.md) | Retain its existing precise contract; remove duplicate and stale draft/action-plan guidance. |
| Tool schemas and descriptions as model-facing instructions; typed tool registration | [Tool definition and toolbox](contracts/tool-definition-and-toolbox.md) | Link to it; do not restate schema guidance in the parent index. |
| Agent purpose, decision boundaries, and state/tool classification | [State and tool taxonomy](application-states/state-and-tool-taxonomy.md) and [Agentic state framework](runtime/agentic-state-framework.md) | Keep application classification and reusable runtime responsibilities in their respective owners. |
| Optional reasoning/planning preparation and structured artifacts | [Agentic-state preparation](runtime/agentic-state-preparation.md) | Retain the accepted configurable feature; retire global planner/action executor proposals. |
| Prompt behavior, concise instructions, examples, and avoiding repeated backend guarantees | [Prompting guidelines](context-and-prompts/prompting-guidelines.md) | Link to the prompt-specific owner. |
| Provider call identity, tool execution, exactly one matching output, nested agents, pausing, and recovery | [Tool-calling protocol](runtime/tool-calling-protocol.md) | Preserve this as the only provider-loop contract. |
| Master and state-local history, selection, child boundaries, and paused continuation | [Agentic history session](runtime/agentic-history-session.md) | Preserve this as the only history-ownership contract. |
| Minimum sufficient model context and safe channel projection | [Context package contract](context-and-prompts/context-package-contract.md) | Link to the context owner. |
| Dynamic model-facing references and owner projection | [Reference context and owner projection](context-and-prompts/reference-context-and-owner-projection.md) | Retain the run-scoped contract; remove static `OWNER`, `NODE_*`, and `CANDIDATE_*` examples. |
| Provider/model request normalization and externally supplied configuration | [Provider integration boundary](providers/provider-integration-boundary.md) | Keep caller-selected routes; remove speculative model-routing policy. |
| Embeddings as derived indexes | [Vector retrieval and indexing](../network/vector-retrieval.md) | Remove the duplicate AI-engineering treatment. |
| Domain nodes versus `MemoryLog` atoms | [MemoryLog model](../network/memory-log-model.md) and [Graph model](../network/graph-model.md) | Remove domain modeling detail from AI-engineering. |
| Repository scope, module layout, DTO annotations, and implementation constraints | [Technical principles](../requirements/technical/technical-principles.md) and [Dependency-oriented module design](../requirements/technical/dependency-oriented-module-design.md) | Do not create a second AI-specific development checklist. |

## Source disposition

### `README.md`

Keep its section map and canonical links. Remove the retained broad baseline
and reduce it to a short purpose statement, index, and navigation guidance.
The final README must not define new AI behavior.

### `contracts/generalized-ai-principles.md`

Review its rules against the ownership map. Preserve no second copy. The current
material includes stale candidate/reference families, generic planning and
write-plan execution, provider-frame terminology, and detailed vector/memory
domain rules. Retire those sections after confirming the canonical owner above
or confirming that the proposal is no longer part of the target.

The general advice to choose deterministic code for simple reliable work and
LLM judgment for semantic ambiguity belongs to the existing state/tool
classification. Speculative routing by difficulty, privacy, latency, or cost
is not made into a new runtime feature by this documentation cleanup.

## Waves

### Wave 1 — Verify canonical ownership (completed)

- Compare both broad sources with every focused owner in the table.
- Confirm that the accepted rules already have a current owner.
- Record only genuine gaps; do not move a rule solely to preserve source text.

**Exit condition:** each retained rule has exactly one owner; outdated proposals
are marked for removal rather than rewritten as current guidance.

### Wave 2 — Retire broad duplicate sources (completed)

- Remove `contracts/generalized-ai-principles.md` from the contracts index and
  delete it.
- Replace `docs/ai-engineering/README.md` with the short section index.
- Remove the completed consolidation ledger from `contracts/README.md` while
  retaining the active contracts index and ownership boundary.
- Keep active, narrower migration notes in other subfolders only where they
  still describe unfinished work in that specific folder.

**Exit condition:** no broad AI-principles body remains beside focused owners.

### Wave 3 — Close and validate

- Remove duplicated AI and runtime decisions from the root documentation
  landing page; point readers to their canonical owners.
- Update root documentation links and migration ledger to reflect completion.
- Search the repository for links to removed sources and stale terminology that
  was unique to the deleted broad material.
- Check Markdown formatting and ensure every surviving concept points to its
  canonical owner.
- Delete this plan and commit the completed index cleanup.

**Exit condition:** the parent and child indexes lead to one current owner per
topic, no deleted-source links remain, and no temporary consolidation plan is
left in the target folder.

## Explicit scope

- This is a documentation consolidation; it changes no runtime behavior.
- It does not authorize adding generic action plans, retry policies, model
  routers, context managers, or new state classifications.
- It does not clean the separate runtime migration plan, UAT fixtures, or
  application-state behavior.
