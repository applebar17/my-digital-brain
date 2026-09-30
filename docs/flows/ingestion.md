# Ingestion flow

## Purpose

Ingestion turns a user-provided memory, update, correction, or derived media
transcript into preserved, source-backed graph knowledge. The user should be
able to share information naturally, understand when a focused clarification is
needed, and receive a final response based on confirmed work rather than an
internal processing trace.

## Functional journey

```text
message or media-derived transcript
  -> source preserved with provenance
  -> relevant existing memory is considered
  -> information is organized into nodes, memories, context, and relationships
  -> ambiguity is clarified only when it matters
  -> confirmed graph outcome is returned to the conversation
```

The internal phased workflow is intentionally ordered because relationships and
memory context depend on known object references. Its technical state sequence
is defined in [deterministic agentic workflows](../architecture/deterministic-agentic-workflows.md).

## User-visible expectations

- Text and supported media sources enter the same memory flow; a transcript is
  preserved as derived evidence linked to its original media artifact.
- The system preserves source evidence, relevant timing, and user wording where
  those facts matter to later interpretation.
- New observations normally become additive `MemoryLog` records or supported
  context, rather than silently overwriting existing people, events, or
  relationships.
- A dense source may create multiple coherent memory records when it describes
  distinct meaningful episodes.
- The system creates durable relationships only when the source supports a
  meaningful connection. Incidental co-presence remains memory involvement.
- The final conversation reply describes the confirmed outcome in plain
  language. It never displays backend identifiers, state names, tool results,
  or internal reasoning.

## Ambiguity and clarification

The system asks a short, human-oriented clarification only when the answer
materially improves identity, memory correctness, safety, or future retrieval.
It should preserve low-precision or uncertain information when interruption is
less useful than capture.

Examples of useful clarification include distinguishing similarly named people,
separating apparently conflicting events, or resolving an identity needed for a
durable relationship. A clarification is part of the current interaction and
resumes the originating work; it is not a completed chat answer or a separate
form workflow.

The channel-neutral behavior, correlation, and answer experience are defined in
[clarification agent and UX](../requirements/functional/clarification-agent-and-ux.md).

## Integrity expectations

- A repeated source must not create duplicate memory facts merely because it is
  processed again.
- Existing identity evidence is considered before creating a new entity, but a
  plausible match never silently merges people or other objects.
- A tool or validation failure remains recoverable information for the invoking
  state whenever possible. It does not become the final user-facing response.
- A relationship that cannot yet be grounded may be deferred while the valid
  memory and node work remains preserved.
- Contradictions are handled as possible conflicts, temporal changes, or
  nuances; the system should not interrupt the user for low-value uncertainty.

## Related documentation

- [Ingestion application states](../ai-engineering/application-states/ingestion/README.md)
- [Entity resolution flow](entity-resolution.md)
- [MemoryLog model](../network/memory-log-model.md)
- [Reference context and owner projection](../ai-engineering/context-and-prompts/reference-context-and-owner-projection.md)
- [Tool-calling protocol](../ai-engineering/runtime/tool-calling-protocol.md)
- [Media ingestion](../external-integrations/media-ingestion.md)
