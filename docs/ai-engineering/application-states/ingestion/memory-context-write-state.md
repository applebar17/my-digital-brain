# Memory and context write state

## Purpose

Create `MemoryLog` records and supported perceptions that describe the memory.
Relationship contexts and their history belong to the later relationship-write
state.

## Why it exists

Once node references are available, the workflow can record the episode without
forcing all information into durable node properties or relationships. This
lets the graph remain useful when details are partial.

## Required context

- normalized input text or transcript;
- reasoning guidance;
- compact results from node resolution/write;
- `ReferenceContext` at level 1 for available node refs and level 2 only for a
  context-specific ambiguity;
- relevant temporal information available in the input.

## LLM convention

Identify coherent memory atoms with a concise user-facing title, short summary,
primary host, involved targets, and supported time/context links. Use multiple
logs only when the input contains distinct meaningful episodes.

Keep weak co-presence as involvement. Do not invent hosts, involved targets,
evidence, temporal facts, media, or context objects outside the supplied refs
and input. Do not silently patch an existing domain node in place of recording
a new observation.

## Tools and clarification

The toolbox exposes only configured deterministic creation capabilities and,
when needed, an agentic tool that invokes `ClarificationAgentState`. A tool may
return a recoverable field/reference error; the state either corrects its typed
arguments, asks clarification, or returns an honest partial result through its
normal caller chain.

## Expected result and handoff

The typed result is a `MemoryContextWriteResultDTO`: created MemoryLog and
perception refs, concise user-meaningful titles/summaries, deferred items, and a
`ReferenceContext` delta. It is compacted for relationship work; raw write
payloads and backend identities do not propagate.

## Prompt contract

The prompt distinguishes durable relationships from log involvement and asks
for fields that the DTO explicitly defines. It does not request arbitrary
metadata or backend-owned persistence fields.

The LLM-facing perception tool accepts a supplied `target_ref`. Its handler
resolves that ref and builds a separate backend-only persistence request
containing the target UUID and typed `PerceptionDTO`; backend identifiers never
enter the provider-facing schema.

## Related documentation

- [MemoryLog model](../../../network/memory-log-model.md)
- [Reference context and owner projection](../../context-and-prompts/reference-context-and-owner-projection.md)
- [Tool definition and toolbox](../../contracts/tool-definition-and-toolbox.md)
