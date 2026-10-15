# Define census scope and disposition labels

**Status: Done**

## Objective

Define the source and test boundaries to inspect before classifying individual
files. Include the entire `my_digital_brain.agentic` package and direct
application consumers; discover indirect callers rather than assuming the
package directory is the whole pipeline.

## File treatment classifications

- **Keep/adapt integration boundary** — stable generic server/API/storage or
  service boundary that remains needed; adapt its runtime dependency if needed.
- **Rebuild from specification** — AI/agentic implementation is replaced in a
  new layer; current code is not ported.
- **Review behavior for migration** — identify specific functional behavior or
  field semantics that may be implemented anew if confirmed useful.
- **Reference only** — useful for understanding current behavior/failures, but
  neither code nor contract is presumed to carry forward.
- **Retire** — no needed role remains after replacement and callers migrate.
- **Decision needed** — evidence or product direction is insufficient; state
  the exact decision rather than guessing.

These labels classify target treatment, not work progress. Use a separate
`Status` field for task/issue progress.

## Standard source-file assessment

Every census entry records only these brief fields:

| Field | Meaning |
| --- | --- |
| Current role | What this file does now. |
| Useful signal | Behavior, data meaning, or contract worth considering. |
| Do not port | Current implementation or assumptions not to carry into the new layer. |
| Treatment | One classification above, plus evidence or an open question if needed. |

## Acceptance

The scope includes every source file under `src/my_digital_brain/agentic/`,
each direct production import/caller, relevant tests, and existing design
documents that claim to specify the current or target behavior. Each discovered
file receives one primary disposition and a rationale; additional notes may
identify behavior worth extracting independently.

## Initial scope discovered

- 23 files under `src/my_digital_brain/agentic/` (core and tools).
- 16 other production files directly importing `my_digital_brain.agentic`.
- The connected `src/my_digital_brain/ingestion/` package (64 files), because
  it contains both the current multi-stage agentic workflow and deterministic
  extraction/context/graph-write collaborators.
- Chat/API and clarification adapters, prompt registry/templates, and the
  active `ai/session/` boundary that the current state runner calls.
- Relevant tests for runtime, tool bindings, history, chat rendering/activity,
  clarification continuation, ingestion stages, contracts, and graph writes.

The user's `ai_clients` implementation is the technical reference baseline
for the new agentic layer, not part of the old application pipeline census.
Compare current boundaries with its stated DTO/tool-call behavior; do not
replicate its files or inherit current agentic implementation structure by
default.

For the ingestion-specific inventories, paths are relative to
`src/my_digital_brain/ingestion/`; `contracts/` and `extractors/` are literal
subdirectories. The task files record individual modules and their initial
rebuild value/disposition.
