# Memory and context write state

## Purpose

Create source-backed `MemoryLog` records and any supported context objects that
describe the memory itself, such as a perception or relationship context.

## Why it exists

Once node references are available, the workflow can record the episode without
forcing all information into durable node properties or relationships. This
preserves provenance and lets the graph remain useful when details are partial.

## Required context

- normalized source or transcript;
- reasoning guidance;
- compact results from node resolution/write;
- `ReferenceContext` at level 1 for available node refs and level 2 only for a
  context-specific ambiguity;
- source/evidence projection and relevant temporal information.

## LLM convention

Identify coherent memory atoms with a concise user-facing title, short summary,
primary host, involved targets, and supported time/context links. Use multiple
logs only when the source contains distinct meaningful episodes.

Keep weak co-presence as involvement. Do not invent hosts, involved targets,
evidence, temporal facts, media, or context objects outside the supplied refs
and source. Do not silently patch an existing domain node in place of recording
a new observation.

## Tools and clarification

The toolbox exposes only configured deterministic creation capabilities and the
shared clarification tool. A tool may return a recoverable field/reference
error; the state either corrects its typed arguments, asks clarification, or
returns an honest partial result through its normal caller chain.

## Expected result and handoff

The typed result is a `MemoryContextWriteResultDTO`: created MemoryLog and
context refs, concise user-meaningful titles/summaries, deferred items, and a
`ReferenceContext` delta. It is compacted for relationship work; raw write
payloads and backend identities do not propagate.

## Prompt contract

The prompt distinguishes durable relationships from log involvement and asks
for fields that the DTO explicitly defines. It does not request arbitrary
metadata or backend-owned provenance fields.

## Related documentation

- [MemoryLog model](../../../network/memory-log-model.md)
- [Reference context and owner projection](../../context-and-prompts/reference-context-and-owner-projection.md)
- [Tool definition and toolbox](../../contracts/tool-definition-and-toolbox.md)
