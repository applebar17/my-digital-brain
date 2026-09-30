# Memory maintenance and corrections

**Status:** future functional requirement. This is not an MVP commitment, a
current agent, a toolbox, or an automatic background job.

## Purpose

Memory maintenance lets an owner correct, contextualize, confirm, dispute,
archive, or remove information over time without treating the memory graph as a
database administration interface. It protects trust in the memory while
preserving the evidence and history needed to explain a change.

## Product principles

- Preserve source evidence and historical values instead of silently overwriting
  them.
- Make consequential changes explicit, reversible where possible, and
  attributable to an owner, source, reason, and time.
- Ask for confirmation before destructive changes or identity merges and splits.
- Ask a focused clarification only when the available context cannot safely
  retain both interpretations.
- Do not interrupt the owner for every apparent inconsistency: different times,
  participants, or sources may describe compatible memories.
- Do not run maintenance proactively by default. A future proactive capability
  needs an explicit product policy and evidence threshold.

## Functional scenarios

### Correcting a mutable fact

The owner says: “Luca's current phone number is Y, not X.”

The application identifies the affected fact and its evidence, retains X as a
historical value, and proposes Y as the current value. It asks for confirmation
when the change is consequential. Future queries use Y by default while still
being able to explain that X was previously recorded.

### Interpreting an apparent conflict

A prior memory places an apparently identical dinner in Milan, while a new
memory says Turin. The application considers time, participants, and evidence
before treating the records as contradictory. It asks whether they are distinct
events only when both cannot be retained safely.

### Reviewing a possible duplicate

Two records may refer to the same Marco. The application presents meaningful
distinguishing evidence, aliases, sources, and historical clues. A merge needs
owner confirmation; the original records and the decision trail remain
available. A future review may instead retain both identities or split an
incorrectly merged record.

### Managing lifecycle and evidence

An owner can confirm, dispute, archive, expire, or delete a memory, attach or
detach evidence, and correct a source contact or metadata. The UI explains the
visible outcome, such as an expired phone number no longer appearing as current
while its historical record remains available.

## User experience

The owner starts maintenance through ordinary chat, a memory detail view, or a
future explicit review surface. It should show the relevant evidence, current
and historical values, and a concise explanation of any proposed change; it
should not expose raw database identifiers or operational traces.

Examples:

- “I found two memories that may describe the same person. Are they the same?”
- “I have an older phone number and a newer one. Should I mark the older one as
  expired?”
- “These accounts of the dinner differ. Were they separate events?”

## Boundaries and dependencies

- [Memory lifecycle](../../network/memory-lifecycle.md) defines lifecycle
  semantics and audit expectations.
- [Entity resolution](../../flows/entity-resolution.md) defines current
  identity-resolution behavior.
- [Clarification agent and UX](clarification-agent-and-ux.md) defines the
  human-facing clarification contract.

Future state and tool conventions are documented only after the corresponding
product behavior is approved.

## Acceptance expectations

- A correction does not silently discard the prior supported value.
- A merge, split, deletion, or other consequential action asks for confirmation.
- An apparent conflict is contextualized before a question is asked.
- The owner can understand what will change and why without technical IDs.
