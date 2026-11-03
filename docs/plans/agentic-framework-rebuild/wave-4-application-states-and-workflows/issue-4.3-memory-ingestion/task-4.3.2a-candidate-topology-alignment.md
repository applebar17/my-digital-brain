# Task 4.3.2a — align graph topology with candidate types

**Status: Not started**

## User story

As the ingestion workflow, I need candidate types accepted by the read-only
candidate state to have coherent graph contracts before node writes begin.

## What and why

Before Task 4.3.3 writes candidates, align the canonical graph topology,
deterministic graph interface, typed persistence DTOs, and model-facing write
tools with the accepted candidate taxonomy. In particular, migrate the existing
standalone `Topic` representation into `KnowledgeItem` and add the kinds
`topic`, `concept`, `idea`, `insight`, `reminder`, `quote`, `reference`, and
`other`.

This task does not change Task 4.3.2 candidate generation and does not add a
second candidate schema. User-facing graph presentation is updated only where
the new labels require readable titles or categories.

## Where

- Canonical graph topology and relevant network documentation.
- Target graph contracts, services, repositories, and typed write functions.
- Product graph tools required by Task 4.3.3.
- Graph presentation mapping for the accepted new node labels.

## Dependencies and acceptance

- Depends on Task 4.3.2's accepted candidate contracts.
- Completes before Task 4.3.3 node resolution and writes.
- Candidate DTOs map one-to-one to explicit backend write DTOs without generic
  property bags or backend identifiers entering model context.
- Topic and concept information is consistently represented through
  `KnowledgeItem` across topology, persistence, tooling, and human-readable
  graph presentation.
