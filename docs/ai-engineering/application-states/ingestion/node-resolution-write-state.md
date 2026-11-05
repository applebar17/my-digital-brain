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

## Deterministic batching

The workflow partitions the candidate inventory before invoking this state.
Batching is deterministic and configured at application launch. The default
policy uses a maximum batch size of 15 candidates and a dedicated-type minimum
of 5:

1. emit complete type-specific batches up to the maximum size;
2. emit a dedicated type-specific batch for a remainder at or above the
   dedicated-type minimum; and
3. pool smaller remainders into mixed batches up to the maximum size.

Both values are launch configuration, not hard-coded state behavior. Batches
execute sequentially over the same `ReferenceContext`. Identity lookup runs
immediately before each batch, so nodes created or updated by an earlier batch
are available as evidence to later batches. The state class is unchanged by
batch composition; its toolbox is narrowed to the node types present in the
current batch.

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
capabilities configured for this state and, when needed, an agentic tool that
invokes `ClarificationAgentState`. A tool error remains a detailed tool output
for this state to address; it does not end the workflow.

If clarification is required, this state delegates the doubt to
`ClarificationAgentState`. The child asks the user through its deterministic UI
interaction tool; after the child completes, this state receives the child's
typed result as the matched output of its original agentic tool call.

## Expected result and handoff

The model-facing typed result contains one explicit outcome per candidate:
created, selected existing, updated existing, or deferred. The deterministic
batch handler combines those outcomes with the trusted `ReferenceContext`
delta produced by successful tools. Neither result contains provider
transcripts or model-visible backend IDs.

The workflow merges each completed batch into the shared reference context
before looking up and invoking the next batch. It exposes the combined result
to memory/context work only after every batch completes.

## Existing-node updates

Selecting an existing reference and updating it are separate decisions. The
state may select a supplied existing reference without changing it, or invoke
the explicit subtype update action when the candidate or a clarification adds
grounded information.

Update DTOs are subtype-specific. Nullable scalar fields mean unchanged when
null, aliases are additive, and field clearing is outside the current scope.
The state handles conflicting identity information semantically, invoking
clarification when needed; deterministic validation or write failures return
as ordinary tool errors and do not terminate the provider interaction.

## Prompt contract

The prompt must clearly label lookup results as evidence and explain the
difference between an existing supplied ref, a new candidate, and an unresolved
identity. It must require tool use for actual writes and prohibit a final
assistant message from standing in for a write result.

## Related documentation

- [Entity resolution flow](../../../flows/entity-resolution.md)
- [Tool-calling protocol](../../runtime/tool-calling-protocol.md)
- [Clarification agent and UX](../../../requirements/functional/clarification-agent-and-ux.md)
