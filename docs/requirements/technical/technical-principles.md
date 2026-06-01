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
- Metadata and enrichment proposals.

## Agentic But Guarded

The MVP should allow an agentic AI Manager to handle dynamic conversational cases instead of hard-coding every possible flow upfront.

The system should separate:

- Dynamic decisions: message intent, clarification style, tool selection, correction suggestions, and conversational recovery.
- Guarded operations: graph writes, source storage, entity resolution decisions, privacy checks, and provenance.

The AI Manager can be flexible. The Network API and graph mutation layer should remain structured, validated, and auditable.

Not every edge case needs explicit deterministic handling in v1. The system should keep a small set of safe tools, persist minimal pending state, expire abandoned processes, and add more explicit handling only when real usage proves it necessary.

The conversational LLM chooses actions and proposes parameters. Backend services validate parameters, own process state, and perform all state changes. Top-level tools should remain few and stable: start memory ingestion, query memory context, and propose memory correction. Resume, cancel, expire, validation, clarification handling, and write execution are backend process operations, not broad conversational tools.

Pending process state should be treated as context for future runtime or agent calls, not as a rigid route that consumes the next message automatically. Conversation history should be available for context building, while the model-facing context remains scoped and low-noise.

## Idempotent Ingestion

Ingestion should be resumable and idempotent. Reprocessing the same source should not create duplicate entities or relationships.

This requires stable source identifiers, extraction run identifiers, deduplication checks, and merge policies.

Structured ingestion objects should sit between extraction and graph writes. The graph writer should consume validated write plans, not raw LLM output.

Clarification state should be minimal. It exists so the AI Manager can resume a pending ingestion after a later chat message when appropriate, not as a separate clarification subsystem or strict workflow engine.

Ingestion complexity should be decided after a cheap mention scan and compact graph-context retrieval. Raw text alone is not enough to know whether an ingestion is simple, ambiguous, contradictory, or relationship-heavy. The ingestion planner should propose extraction tasks, not graph writes.

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
- Update or expire contact details.
- Edit, disable, or delete profile memories.
- Promote useful metadata into typed fields or relationships.

Corrections should become signals for future resolution.

## Privacy And Security

The system stores personal memory and must be designed as sensitive software.

Baseline requirements:

- Avoid unnecessary data exposure to third-party services.
- Treat contact details, addresses, and external identifiers as sensitive data.
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
- Enrichment requests, cached values, provider provenance, and expiration status.

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

## External Enrichment

External tools may enrich entities, but enrichment must remain distinguishable from user-provided memory.

Rules:

- Store provider, retrieval time, input, confidence, and expiration policy.
- Check provider terms and privacy constraints before storing or redisplaying external data.
- Prefer runtime lookup when data changes often or should not become canonical memory.
- Prefer stored enrichment when the value is stable, confirmed, useful offline, or important for resolution.
- Cache with expiration when the data is useful but freshness matters.
