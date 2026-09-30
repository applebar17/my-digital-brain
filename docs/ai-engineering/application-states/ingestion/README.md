# Ingestion application states

This folder defines the internal LLM conventions for the deterministic
memory-ingestion workflow. Each document states why one LLM-backed state exists,
the context it may use, its decision boundaries, expected typed result, and its
compact handoff to the next workflow dependency.

These documents are the behavioral source of truth. Versioned prompt templates
implement the conventions; they do not replace them. Provider transcripts,
tool-call pairing, shared history, reference rendering, and tool declaration
formats remain owned by their dedicated AI-engineering documents.

## State sequence

```text
ingestion reasoning
  -> node candidate
  -> deterministic identity lookup
  -> node resolution/write
  -> memory/context write
  -> relationship write
```

Identity lookup is a deterministic backend capability between the two node
states. It supplies bounded evidence and reference entries; it does not make
the semantic resolution decision.

## Contents

- [Ingestion reasoning state](ingestion-reasoning-state.md)
- [Node candidate state](node-candidate-state.md)
- [Node resolution and write state](node-resolution-write-state.md)
- [Memory and context write state](memory-context-write-state.md)
- [Relationship write state](relationship-write-state.md)

## Shared boundaries

- Every state receives a purpose-specific DTO, selected history, and only the
  context package it needs.
- Model-facing object references come exclusively from `ReferenceContext`.
- A state uses the default reference rendering level 1 unless a concrete
  decision requires level 2.
- A deterministic tool or child-state error returns as one actionable tool
  output to its invoker; it never terminates the provider conversation.
- A clarification pauses the requesting state and resumes that same state by
  appending the matching provider tool output.
- A state returns a compact typed result and reference delta, never its raw
  provider transcript, internal reasoning, or backend identifiers.
- Each state owns a small proposal/result DTO for its specific handoff. The
  next deterministic write receives an explicit command DTO; persisted records
  receive backend-owned identifiers and provenance only after that boundary.

## Related documentation

- [Deterministic agentic workflows](../../../architecture/deterministic-agentic-workflows.md)
- [Agentic state framework](../../runtime/agentic-state-framework.md)
- [Context package contract](../../context-and-prompts/context-package-contract.md)
- [Reference context and owner projection](../../context-and-prompts/reference-context-and-owner-projection.md)
- [Tool definition and toolbox](../../contracts/tool-definition-and-toolbox.md)
