# Canonical Reference Context

## Goal

Use one coherent, run-scoped reference context for every agentic state and
ingestion phase. The model sees stable, readable references; the backend owns
the mapping from those references to database UUIDs. No active compatibility
path or second reference vocabulary remains in the MVP codebase.

## Locked Direction

- `RefContext` is the only model-facing reference context.
- A context is created once for an ingestion/chat run and inherited by every
  child frame.
- Existing graph objects receive stable readable refs such as `node_0001` and
  carry a backend-only UUID.
- New objects receive readable proposed refs such as `node_new_lorenzo` and
  have no backend UUID until a deterministic write succeeds.
- Clarification packets, plans, tool arguments, and compact child results use
  the same refs. They do not contain database UUIDs.
- UUID resolution and proposal binding happen only in deterministic backend
  services immediately before or after graph writes.
- Persisted frames retain the backend-only reference snapshot needed to resume
  the same run without renumbering or reinterpreting refs.
- Ref context deltas are merged into the existing run context; states never
  rebuild a new context from retrieval results.
- Unknown, stale, cross-run, wrong-kind, or invented refs fail visibly at the
  backend boundary. They are not silently converted or passed to the graph.

## Current Duplication To Remove

The repository currently has two active systems:

1. `agentic/refs.py` with readable `RefContext` refs such as
   `node_new_lorenzo`;
2. `ingestion/reference_registry.py` with uppercase `NODE_*` and
   `CANDIDATE_*` refs.

The clarification toolbox is wired to the second system, while agentic
planning contracts and prompts use the first. The production chat path also
does not initialize either system for `ingest_memory`.

The fix must not introduce a permanent adapter that allows both vocabularies.
During migration, any temporary conversion is internal and short-lived; it
must be deleted in the cleanup wave together with its tests and documentation.

## Target Data Flow

```text
chat message
  -> create RefContext for the run
  -> hydrate retrieved UUIDs into stable existing refs
  -> reason and plan using the model-facing projection
  -> pass the same context to child frames
  -> create a clarification packet using those refs
  -> persist frame + backend-only snapshot
  -> resume with the same packet refs
  -> resolve refs to UUIDs in deterministic write services
  -> bind created UUIDs to the same refs
```

Example:

```text
node_0001          -> Lorenzo Tordini UUID
node_0002          -> Milano UUID
node_new_lorenzo  -> no UUID yet
memory_new_event  -> no UUID yet
```

The model sees the ref, kind, label, name, summary, aliases, and resolution
status. It never receives the UUID or registry scope metadata.

## Delivery Waves

### Wave 0: Contract and inventory

- Treat this plan as the reference policy for the MVP.
- Inventory every producer and consumer of `RunReferenceRegistry`,
  `reference_registry_snapshot`, `alias_map`, `RefContext`, and raw graph IDs.
- Define one snapshot format and one model-facing projection.
- Add contract fixtures covering retrieval, planning, clarification, resume,
  creation, and UUID binding.

### Wave 1: Canonical context implementation

- Move the shared `RefContext` implementation to a non-agent-specific core
  module if necessary.
- Add safe registration, proposal allocation, lookup, UUID binding, snapshot,
  restore, and delta-merge operations.
- Make object-kind and resolution-status enums canonical.
- Ensure proposed refs accept the readable names used by the active prompts.
- Keep backend UUIDs out of `model_facing_packet()`.

### Wave 2: Retrieval and ingestion initialization

- Create the context at the chat ingestion boundary.
- Hydrate every retrieved graph object into the context before reasoning.
- Replace loose retrieval aliases and raw graph IDs in model-facing packages
  with canonical refs.
- Carry the context through memory ingestion, all plans, and action payloads.

### Wave 3: Tool and graph boundary migration

- Update clarification lookup, context projection, and question validation to
  consume `RefContext` directly.
- Make graph tools accept model refs and resolve them internally to UUIDs.
- Return canonical refs and context deltas from writes, never raw UUIDs as the
  primary model result.
- Remove raw-ID target fields from model-facing action contracts.

### Wave 4: Durable interruption and resume

- Persist the canonical context snapshot in the interrupted child frame.
- Ensure a pending clarification tool creates exactly one interrupted frame.
- Resume with the same ref values and merged answer context.
- Add an API-level end-to-end test using the existing Lorenzo/Milano story:
  message, structured packet, refresh, answer, UUID resolution, and final
  response.

### Wave 5: Cleanup

- Delete `ingestion/reference_registry.py` and its exports after all consumers
  migrate.
- Remove `reference_registry_snapshot` and `alias_map` as independent contract
  fields; retain only the canonical context snapshot/projection.
- Delete compatibility conversion helpers, raw-ID clarification paths, and
  duplicate registry tests.
- Update UAT scripts and architecture documents to use the canonical context.
- Run a repository-wide search to confirm no deprecated vocabulary or imports
  remain outside historical decision records.

## Completion Criteria

- One ref in a run has one meaning across retrieval, planning, clarification,
  resume, and writes.
- Refreshing or switching chats does not change refs.
- Clarification packets validate without database IDs.
- Every UUID used by a graph operation came from backend resolution of a known
  canonical ref.
- No legacy registry, compatibility alias, raw-ID model contract, or stale
  documentation remains in active code.
