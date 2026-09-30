# Node resolution and write state

## Purpose

Resolve a node candidate using bounded identity evidence and, when justified,
invoke the configured deterministic node-write capability. It is the first
state that may create a node or attach new information to an existing one.

## Why it exists

Lookup is deterministic evidence, while identity is a semantic decision. This
state keeps those responsibilities separate: backend code determines what may
be safely considered; the LLM decides whether the supplied evidence supports
reuse, a new object, or clarification.

## Required context

- one `NodeCandidateDTO` or a compact batch of independent candidates;
- bounded deterministic identity-lookup evidence for each candidate;
- `ReferenceContext` at level 2 for candidate matches and level 1 for other
  relevant objects;
- source grounding, reasoning guidance, and active owner projection where
  relevant.

## LLM convention

Choose only from a supplied existing reference, a new object supported by the
candidate, or clarification where the decision materially affects identity.
Do not invent a reference, persisted ID, graph match, merge, or property value.

When selecting an existing object, preserve new information through additive
memory, context, or relationship work unless an explicit typed property update
is supported and evidenced. A plausible or fuzzy match is not an automatic
identity binding.

## Tools and clarification

The toolbox contains only the deterministic, typed node resolution/write
capabilities configured for this state and the shared clarification tool when
needed. A tool error remains a detailed tool output for this state to address;
it does not end the workflow.

If clarification is required, the state asks one user-oriented question using
the existing clarification protocol. The state pauses and later resumes with
the answer as the matching tool output.

## Expected result and handoff

The typed result is a `NodeResolutionWriteResultDTO`: created or selected
model-facing refs, concise semantic outcome, additive changes made when any,
deferred items, and a typed `ReferenceContext` delta. It contains no provider
transcript or backend IDs.

The workflow merges the reference delta before preparing memory/context work.

## Prompt contract

The prompt must clearly label lookup results as evidence and explain the
difference between an existing supplied ref, a new candidate, and an unresolved
identity. It must require tool use for actual writes and prohibit a final
assistant message from standing in for a write result.

## Related documentation

- [Entity resolution flow](../../../flows/entity-resolution.md)
- [Tool-calling protocol](../../runtime/tool-calling-protocol.md)
- [Clarification agent and UX](../../../requirements/functional/clarification-agent-and-ux.md)
