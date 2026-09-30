# Architecture documentation migration

**Status:** transitional migration plan. Delete this file once the Architecture
folder contains only its current cross-component specifications and every
inbound reference has been updated.

## Purpose

The clean-slate runtime and application-state documentation now has canonical
owners under `docs/ai-engineering/`. This plan removes the older competing
agentic-runtime, reference, planning, and pending-process narratives from
`docs/architecture/` without losing valid component and workflow decisions.

Architecture retains system decomposition and workflow coordination. It does
not retain a second specification for provider transcripts, tool loops, prompt
templates, state-local history, reference rendering, or generic agent plans.

## Target folder structure

```text
docs/architecture/
  README.md
  overview.md
  deterministic-agentic-workflows.md
```

| Target file | Long-term responsibility |
| --- | --- |
| `README.md` | Concise folder purpose and index. No migration ledger once complete. |
| `overview.md` | Component ownership, system boundaries, deployment posture, and data lifecycle. |
| `deterministic-agentic-workflows.md` | MVP workflow scheduling, dependency order, typed state handoffs, approved parallelism, and future coordinator boundary. |

No new Architecture document is needed for AI internals. Those concepts already
have focused owners.

## Canonical ownership map

| Concept formerly described in Architecture | Canonical owner |
| --- | --- |
| Provider tool-call/output pairing, nested agent tools, failures, and paused continuation | [Tool-calling protocol](../ai-engineering/runtime/tool-calling-protocol.md) and [Agentic history session](../ai-engineering/runtime/agentic-history-session.md) |
| Base agentic state, invocation/result DTOs, and configured toolboxes | [Agentic state framework](../ai-engineering/runtime/agentic-state-framework.md) |
| Reasoning/planning preparation calls | [Agentic-state preparation](../ai-engineering/runtime/agentic-state-preparation.md) |
| Tool schemas, registered handlers, validation, and tool outputs | [DTO-first contracts](../ai-engineering/contracts/dto-first-contracts.md) and [Tool definition and toolbox](../ai-engineering/contracts/tool-definition-and-toolbox.md) |
| Prompt templates, versions, and runtime rendering | [Prompt lifecycle and versioning](../ai-engineering/context-and-prompts/prompt-lifecycle-and-versioning.md) |
| Model-facing object references, dynamic owner projection, and rendering levels | [Reference context and owner projection](../ai-engineering/context-and-prompts/reference-context-and-owner-projection.md) |
| Ingestion-state purpose, context, and typed handoffs | [Ingestion application states](../ai-engineering/application-states/ingestion/README.md) |
| Product-facing future correction and maintenance behavior | [Memory maintenance and corrections](../requirements/functional/memory-maintenance-and-corrections.md) |

## Source disposition

| Existing source | Preserve or migrate | Retire |
| --- | --- | --- |
| `agentic-orchestration.md` | Purpose-specific states, constrained toolboxes, bounded context, compact child results, and versioned prompts are already migrated to AI engineering. | Pending-process routing, `AS`/`BP`/`LP`/`RS` taxonomy, static handoff graph, generic write plans, and the old state inventory. |
| `agentic-tool-frame-runtime.md` | Conversation entry, nested agent-as-tool behavior, history descends/compact result ascends, and clarification continuation are already migrated. | `AgenticFrame`, `MemoryPlan`, `MemoryPlanAction`, generic creation/update frames, and its old implementation waves. |
| `ingestion-identity-resolution-and-context-packets.md` | Bounded deterministic lookup, lookup as evidence rather than automatic binding, no raw IDs, additive updates, and explicit structured correction after clarification are already migrated. | Mandatory rigid lookup staging, static `OWNER`, `NODE_*`/`CANDIDATE_*` aliases, generic resolution executor, write plan, and ordinary-history clarification continuation. |
| `memory-ingestion-reasoning-planning-and-llm-refs.md` | Task-specific context, compact state results, reasoning before dependent work, and resolved references before relationship work are already migrated. | Generic plan/action executor, broad state prompt registry, old reference families, and its implementation waves. |
| `overview.md` | Keep its component, storage, deployment, and lifecycle responsibilities. | Pending-ingestion/latest-Telegram resume wording, a misleading fully-dynamic orchestration description, and future capabilities stated as active states. |
| `deterministic-agentic-workflows.md` | Keep as the current MVP workflow coordinator contract. | No generic action plan or provider-runtime detail may be added. |

## Migration waves

### Wave 1 — Establish the retained architecture boundary

Update `overview.md` and `deterministic-agentic-workflows.md` only where
needed to make their roles unambiguous.

- Define the AI Manager as agentic in semantic decisions and deterministic in
  approved workflow scheduling, dependency handoff, validation, and writes.
- Replace “latest pending ingestion” and channel-specific resumption with the
  generic paused-state continuation owned by the provider tool protocol.
- Keep future profile, correction, and maintenance capabilities as product
  capabilities until their states and tool contracts are approved.
- Keep the workflow as the sole MVP coordinator; it may later be replaced by
  agent-to-agent coordination only if state entrypoints and DTO contracts stay
  stable.

**Exit condition:** the two retained documents link outward for AI-runtime
detail and contain no old pending-process, static-reference, or generic-plan
contract.

### Wave 2 — Retire superseded architecture sources

Before deletion, audit direct Markdown links and search for terms that would
leave a live reference to the four source documents. Update any such links to
the canonical owner in the ownership map.

Delete:

- `agentic-orchestration.md`;
- `agentic-tool-frame-runtime.md`;
- `ingestion-identity-resolution-and-context-packets.md`;
- `memory-ingestion-reasoning-planning-and-llm-refs.md`.

Do not reproduce a retired concept merely to preserve historical detail.

**Exit condition:** only `README.md` remains as an internal reference before
it is cleaned in the next wave; no documentation or code links to a deleted
architecture source.

### Wave 3 — Finalize Architecture indexing

- Reduce `architecture/README.md` to its folder purpose and two retained
  documents.
- Remove its temporary migration ledger.
- Update the root documentation index only if its Architecture descriptions
  need wording changes.
- Delete this migration plan.

**Exit condition:** the target folder structure is exact and every retained
file has one non-overlapping responsibility.

### Wave 4 — Align dependent product documentation

This companion wave is outside the Architecture folder but required to remove
contradictory behavior claims discovered during its review.

Review and update:

- `docs/mvp/baseline.md`;
- `docs/requirements/functional/core-capabilities.md`;
- `docs/requirements/ui/frontend-ui-product-requirements.md`;
- `docs/requirements/technical/technical-principles.md`.

Replace pending-process identifiers, latest-ingestion routing, and generic
sidecar assumptions with user-facing waiting/clarification behavior and the
canonical paused-state tool continuation. UI status may describe visible
activity, but it must not define backend routing.

**Exit condition:** product, UI, MVP, technical, workflow, and runtime
documentation all describe the same clarification model.

## Implementation-boundary reminders

The following DTOs will be designed with their concrete implementations, not
invented in this documentation migration:

- bounded identity lookup request/evidence DTOs;
- state-specific node, memory/context, and relationship proposal/result DTOs;
- explicit deterministic graph-write command DTOs;
- persisted continuation DTO for a clarification-paused state.

They must be purpose-specific. This plan does not authorize a generic graph
plan, action executor, reference family, or new orchestration layer.

## Validation checklist

- The folder contains only its target files when complete.
- No link refers to a deleted Architecture source.
- `overview.md` contains no “latest pending ingestion” or channel-specific
  resume contract.
- The workflow contains no provider transcript mechanics, generic action plan,
  or static owner/reference format.
- Clarification is described consistently as a paused state resumed by one
  matched tool output.
- All retained AI concerns point to their canonical AI-engineering owner.
