# Technical Principles

## Canonical Store

The graph database is the canonical memory store. Other stores may exist for files, embeddings, queues, logs, and analytics, but user-facing memory state is represented through graph entities, relationships, and evidence.

The system may also maintain derived artifacts such as profile summaries, embedding indexes, search indexes, and cache files. These artifacts should be rebuildable from canonical stores.

## Codebase Hygiene And Module Boundaries

The repository should remain understandable as features are added. New code
and code being edited must:

- avoid introducing deprecated paths, duplicate implementations, or hidden
  fallbacks;
- use one clear responsibility per module;
- keep new feature modules below 500 lines, with approximately 450 lines as a
  preferred working target;
- place substantial new behavior in focused modules instead of growing an
  existing monolith;
- keep contracts, orchestration, storage adapters, validation, rendering, and
  tests separated by responsibility;
- update tests and documentation whenever touched behavior or public
  contracts change.

Existing large or uncertain code is not automatically legacy and should not
be refactored without a concrete reason. Refactoring is justified when it is
needed for a clean boundary, safe feature integration, or removal of a
confirmed obsolete path. Compatibility code is acceptable only when it
protects a current external contract and has an identified owner, tests, and
an explicit removal condition.

## Explicit Scope And Minimum Design

Development must implement the behavior explicitly accepted by the product
owner, and no more. Agents and developers may identify an additional concern
and propose a small, concrete solution, but must not add it to the codebase
until that solution is expressly accepted.

In particular, do not introduce internal processing statuses, API or UI payload
fields, validation gates, fallback paths, retry behavior, background work, or
agentic routing/state logic merely because they might be useful. Each must have
a confirmed user, functional, operational, or contractual need.

When requirements are uncertain, preserve the smallest correct path that meets
the accepted behavior. Stop and request a decision before adding a new
observable behavior, state transition, cross-boundary contract, or failure
policy. Prefer deleting an unaccepted implementation over retaining it as a
"just in case" compatibility or extensibility mechanism.

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

Not every edge case needs explicit deterministic handling in v1. The system
should keep a small set of safe tools, persist a minimal paused continuation
only when external input is awaited, expire it under an approved policy, and
add more explicit handling only when real usage proves it necessary.

The conversational LLM chooses actions and proposes parameters. Backend services
validate parameters, own continuation state, and perform all state changes.
Top-level tools remain few and stable: `query_memory` and `ingest_memory`.
Clarification is a configured pausing tool; validation, continuation, and write
execution are runtime or backend responsibilities, not broad conversational
tools.

Conversation history remains available for context building while model-facing
context stays scoped and low-noise. A paused provider call resumes only through
its matching tool output; a generic pending-process route must not consume the
next user message.

Normal chat renders one final user-facing assistant message. Activity events
and clarification interaction packets are separate UI data; technical
diagnostics stay in developer observability rather than a general chat sidecar.

Visible chat history and state-local/provider history are separate concepts.
`AgenticHistorySession` owns state-run and paused-continuation linkage instead
of mixing ingestion state into the chat runtime.

## Idempotent Ingestion

Ingestion should be resumable and idempotent. Reprocessing the same source should not create duplicate entities or relationships.

This requires stable source identifiers, extraction run identifiers, deduplication checks, and merge policies.

Purpose-specific proposal DTOs should sit between model output and graph writes.
The graph writer consumes explicit validated command DTOs, never raw LLM output
or a generic write plan.

Clarification state is minimal and exists only to resume the originating paused
state through its matching tool output. It is not a separate clarification
subsystem or strict workflow engine.

Ingestion receives bounded graph context before semantic work. A state may use
configured reasoning or planning preparation, but neither produces graph writes
or DB-shaped tasks. Deterministic services validate explicit DTOs and execute
the supported commands.

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
