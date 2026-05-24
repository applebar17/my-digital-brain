# Technical Principles

## Canonical Store

The graph database is the canonical memory store. Other stores may exist for files, embeddings, queues, logs, and analytics, but user-facing memory state is represented through graph entities, relationships, and evidence.

The system may also maintain derived artifacts such as profile summaries, embedding indexes, search indexes, and cache files. These artifacts should be rebuildable from canonical stores.

## Provenance First

Every stored fact should be traceable to one or more sources:

- Chat message.
- Clarification answer.
- Uploaded media item.
- Transcript.
- External integration payload.
- Manual frontend correction.
- System inference.

Generated entities and relationships should keep extraction metadata, model identity, timestamp, confidence, and the source span or reference when available.

This also applies to profile memories and arbitrary metadata when they influence retrieval, prompting, entity resolution, or user-visible behavior.

## LLMs As Reasoning Components

LLMs are central to extraction, clarification, summarization, and natural language interrogation. They should not be treated as the database of record.

The system should separate:

- Prompt inputs.
- Model outputs.
- Validation logic.
- Graph write operations.
- User confirmation events.
- Profile memory proposals.

## Idempotent Ingestion

Ingestion should be resumable and idempotent. Reprocessing the same source should not create duplicate entities or relationships.

This requires stable source identifiers, extraction run identifiers, deduplication checks, and merge policies.

## Local And Cloud Portability

The system should be designed to run in both local-friendly and cloud-friendly modes.

Technical requirements:

- Containerized services for backend, databases, workers, and supporting infrastructure.
- Configuration through environment variables or equivalent runtime config.
- No hard dependency on public webhooks for local operation.
- Replaceable LLM and embedding providers, including possible local models.
- Storage abstractions that can map to local files or cloud object storage.
- Backup, export, and restore flows that work locally first.
- Clear separation between private content and operational logs.

## Human-Correctable State

The user must eventually be able to correct the graph:

- Merge duplicate entities.
- Split incorrectly merged entities.
- Edit labels and aliases.
- Mark relationships as wrong.
- Attach or remove evidence.
- Override inferred attributes.
- Edit, disable, or delete profile memories.
- Promote useful metadata into typed fields or relationships.

Corrections should become signals for future resolution.

## Privacy And Security

The system stores personal memory and must be designed as sensitive software.

Baseline requirements:

- Avoid unnecessary data exposure to third-party services.
- Keep raw sources and derived facts access-controlled.
- Log operational metadata without leaking private content when possible.
- Make provider and deployment choices explicit.
- Plan for deletion and export workflows from the beginning.

## Observability

The system should expose enough internal state to debug ingestion and retrieval:

- Source processing status.
- Extraction candidates.
- Clarification state.
- Entity match candidates and scores.
- Merge decisions.
- Graph write results.
- Retrieval traces for answers.

## Evolvable Schema

The graph model will evolve. The first schema should be explicit enough to query but flexible enough to add entity and relation types without large migrations.

Prefer versioned schemas, migration notes, and compatibility layers over implicit ad hoc changes.

## Extensible Metadata

Nodes and relationships may include flexible metadata for variable information that does not yet deserve first-class schema support.

Rules:

- Keep typed fields for core, frequently queried, or behavior-driving facts.
- Use metadata for optional, source-specific, experimental, or display-oriented attributes.
- Track metadata provenance when it matters.
- Promote metadata keys into the schema when they become important.
- Avoid using metadata as an unstructured dumping ground for facts that should be claims or relationships.
