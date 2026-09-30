# Relationship write state

## Purpose

Create or update supported durable relationships only after their endpoints and
any required memory/context objects are available as resolved references.

## Why it exists

Relationship semantics depend on the objects established by earlier workflow
states. Keeping this work last prevents free-form endpoint names, missing
objects, and accidental conversion of ordinary co-presence into graph edges.

## Required context

- normalized source or transcript;
- reasoning guidance about likely durable links;
- compact node and memory/context write results;
- `ReferenceContext` at level 1 for resolved endpoints and relevant context
  refs, with level 2 only where relationship ambiguity needs it.

## LLM convention

Propose a durable relationship only when the source supports a meaningful,
lasting connection. Use exact supplied references for every endpoint. Preserve
the user’s specific wording in the appropriate explicit relationship detail
field when the domain DTO supports it; do not invent a new relationship type or
store semantic detail in an arbitrary property bag.

Incidental attendance, co-presence, or a one-off event belongs in MemoryLog
involvement rather than a durable relationship. If an endpoint is genuinely
missing, use the configured clarification path or return it as a deferred
semantic outcome; do not create an unrelated endpoint just to complete an edge.

## Tools and clarification

The toolbox exposes only deterministic relationship/context write capabilities
configured for this state, plus clarification where needed. Validation or write
errors return to this state as one actionable tool output. The state may retry
with corrected typed arguments, ask clarification, or preserve the memory while
reporting the relationship as deferred.

## Expected result and handoff

The typed result is a `RelationshipWriteResultDTO`: created or updated
relationship/context refs, concise semantic summary, deferred relationships,
and any reference delta. The workflow combines it with prior compact results
into its final ingestion outcome.

## Prompt contract

The prompt supplies permitted relationship semantics through the DTO/tool
schema, not unsupported prose-only fields. It states explicitly that all
endpoints must be supplied refs and that a tool result—not a model assertion—is
the confirmation of a completed write.

## Related documentation

- [Deterministic agentic workflows](../../../architecture/deterministic-agentic-workflows.md)
- [MemoryLog model](../../../network/memory-log-model.md)
- [Tool-calling protocol](../../runtime/tool-calling-protocol.md)
