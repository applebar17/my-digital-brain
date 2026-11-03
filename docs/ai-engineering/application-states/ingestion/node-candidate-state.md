# Node candidate state

## Purpose

Turn the input and reasoning guidance into explicit, typed node candidates
that can be examined against existing graph identity evidence.

## Why it exists

Candidate creation must be distinct from identity lookup and graph writes. The
state can identify what the input appears to mention without controlling graph
search policy, backend identifiers, or persistence behavior.

## Required context

- inherited conversational history selected by the invoking workflow;
- `IngestionReasoningResultDTO`;
- `ReferenceContext` at level 1, including the owner projection when relevant;
- bounded existing-object context useful for aliases and identity cues.

## LLM convention

Produce only the node candidates supported by the input and useful for memory
retrieval. Use known references as recognition context, but leave reference
selection and identity decisions to the later resolution state.

The fixed candidate taxonomy is `Person`, `Event`, `Place`, `Organization`,
`Object`, `Animal`, `SocialCircle`, and `KnowledgeItem`. `KnowledgeItem`
preserves one standalone abstract item with a concise category:

- `topic`: a recurring subject or organizing theme;
- `concept`: a distinct abstract notion or body of thought;
- `idea`: a possibility, proposal, or invention;
- `insight`: a realization, lesson, or principle;
- `reminder`: something the owner wants to remember later, without implying a
  scheduled notification;
- `quote`: exact or memorable wording, with optional attribution;
- `reference`: reusable factual or instructional knowledge; or
- `other`: an abstract item that does not fit the preceding categories.

Treat nicknames and role phrases as possible aliases or identity evidence, not
automatically as separate people. Keep incidental actions, weak co-presence, and
low-salience details out of node candidates when they are better represented as
MemoryLog context.

Do not form graph queries, select matching policy, perform a merge, create a
node, or claim that a candidate is identical to a retrieved object without
sufficient supplied evidence.

## Tools and clarification

The default state has no toolbox. A future explicitly configured read-only
context expansion may be added only if it has a clear candidate-identification
purpose. Clarification is reserved for the later node-resolution/write state,
where bounded lookup evidence is available.

## Expected result and handoff

The typed result is a `NodeCandidateSetDTO`. Each candidate has explicit
semantic node fields, relevant aliases, and any missing identity detail. It
contains no copied source message, message-source identifier, raw UUID,
persisted identifier, graph query, or generic execution action.

The workflow sends every eligible candidate to deterministic identity lookup.
The lookup service allocates any temporary candidate reference needed for its
own bounded evidence packet; the model does not establish a second reference
family.

The workflow derives the candidate types present directly from this result.
Later states may use that set to configure only relevant typed lookup and write
operations; there is no separate pre-census call or duplicate type list.

## Prompt contract

The prompt names available known references and explains that they are evidence
for recognition, not an instruction to reuse them. The output contract exposes
only fields that the next deterministic lookup and resolution state genuinely
need.

## Related documentation

- [Reference context and owner projection](../../context-and-prompts/reference-context-and-owner-projection.md)
- [Deterministic agentic workflows](../../../architecture/deterministic-agentic-workflows.md)
- [MemoryLog model](../../../network/memory-log-model.md)
