# Core Functional Capabilities

This document states the product-level capability requirements. The linked
flow, domain, AI, and UI documents own the detailed behavior and contracts for
each capability.

## Conversational capture

The owner can submit a memory or update through natural interaction. The
application preserves the original source, identifies useful memory content,
and records supported information with its source context. Voice capture is an
early capability: the original audio remains linked to its derived transcript.

The owner can also ask a question, suggest a correction, or answer an active
clarification in the same conversation. The [ingestion flow](../../flows/ingestion.md)
owns the functional sequence and [external integration
requirements](../../external-integrations/README.md) own channel and media
specifics.

## Clarification

When missing or ambiguous context materially affects correctness, the
application can ask a focused question and apply the answer to the existing
work. It should preserve useful low-precision information rather than interrupt
for every uncertainty. The complete user-facing requirement is in
[Clarification Agent and UX](clarification-agent-and-ux.md).

## Identity and entity resolution

The application considers existing graph context when deciding whether new
information refers to an existing entity. It must support incomplete names,
aliases, homonyms, repeated descriptions, and changing facts without silently
merging distinct identities. See [Entity Resolution](../../flows/entity-resolution.md)
for the functional decisions and [Graph Model](../../network/graph-model.md)
for domain semantics.

## Owner profile memory

Stable traits, preferences, vocabulary, and goals can be represented separately
from episodic memories. The owner can inspect and correct this understanding.
Its domain and retrieval behavior are defined in [Personal Profile
Memory](../../network/personal-profile-memory.md).

## Query and retrieval

The owner can ask natural-language questions about stored memories. Answers
must be grounded in relevant graph context and available evidence, and must
communicate uncertainty rather than overstate weak or conflicting support. The
[Interrogation Flow](../../flows/interrogation.md) owns query behavior; retrieval
and indexing semantics are in [Vector Retrieval](../../network/vector-retrieval.md).

## Structured inspection

Advanced users may inspect the graph through structured queries. This is not a
required path for ordinary memory capture or question answering. If exposed, it
must support entity lookup, relationship traversal, and filtering by relevant
time, type, confidence, or source without bypassing normal access controls.

## Graph exploration

The owner can inspect relevant graph neighborhoods, entity and relationship
details, evidence, and available timeline or map context. The [UI
requirements](../ui/README.md) define presentation and interaction; the
[network documentation](../../network/README.md) defines what graph data means.

## Future capabilities

Media beyond voice, owner-facing merge/split actions, and broader external data
sources are staged separately. Their requirements live in [Memory Maintenance
and Corrections](memory-maintenance-and-corrections.md) and [External
Integrations](../../external-integrations/README.md); this document does not
commit them to the MVP.
