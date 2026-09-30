# Architecture overview

## Purpose

This document defines system-level component ownership and the end-to-end data
lifecycle. The visual topology, deployment posture, external dependencies, and
data stores are defined once in the [system architecture](system-architecture.md).

The AI runtime is specified in [AI engineering](../ai-engineering/README.md).
This document does not define provider transcripts, prompt templates, tool
schemas, state-local history, or graph-write DTOs.

## Component responsibilities

### Ingestion interfaces and API gateway

The web frontend, Telegram, and future channels submit text and media through
the API and channel gateway. The gateway authenticates where applicable,
normalizes a channel request into an application request, and returns only
user-safe responses, activity, and clarification packets. Consumers do not
call graph, vector, or AI providers directly.

### AI Manager

The AI Manager is the application boundary for conversational capability. It
uses the conversation entry state to interpret a user interaction and invoke a
configured query, ingestion, or later approved capability.

Semantic decisions are agentic: an LLM state interprets source meaning,
available evidence, ambiguity, and appropriate tool use. Scheduling is
deterministic where dependencies are known: a workflow passes typed compact
results, selected history, and `ReferenceContext` between states in the
declared order. Validation, ID translation, and graph writes remain
deterministic backend responsibilities.

The concrete runtime, history, tool, prompt, and state contracts belong to
[AI engineering](../ai-engineering/README.md). The current scheduling boundary
is [deterministic agentic workflows](deterministic-agentic-workflows.md).

### Memory network services

Memory network services provide stable graph-domain operations:

- entity, relationship, claim, context, and memory-log storage;
- source and evidence linking;
- graph query, retrieval hydration, and statistics;
- deterministic identity lookup evidence and bounded context construction;
- domain validation, auditability, and private-ID translation.

They never receive provider-native objects or permit model-authored database
operations. Model-facing references are run-scoped `ReferenceContext` entries;
the active owner is a safe projection, never a backend identifier.

### Source, media, and asynchronous processing

Source services preserve raw text, attachments, transcripts, and user
confirmations. Media processing creates derived artifacts, such as speech-to-
text transcripts, while retaining the original artifact as the evidence anchor.

Background workers run explicitly queued work such as transcription, embedding
refresh, and approved asynchronous jobs. They do not own interactive provider
continuation or user-facing chat routing.

### Retrieval and query

Retrieval combines semantic search with graph hydration and evidence-aware
answer generation. The vector index accelerates semantic lookup but is never
the memory source of truth. Its current boundary is defined in
[vector retrieval and indexing](../network/vector-retrieval.md).

### Future capabilities

Personal profile memory, owner-facing corrections, contradiction review, and
memory maintenance are product capabilities. They become concrete states only
when their purpose-specific DTOs, tools, and workflow dependencies are
approved; they are not active architecture modules by name today.

## Clarification boundary

Clarification is part of the requesting agentic state, not a separate public
API or a generic pending-process router. A clarification tool call pauses that
state's provider transcript. The user's answer supplies one matching tool
output, and the same state resumes with its preserved typed context and
reference context.

The API may expose an understandable waiting state to the frontend or Telegram,
but that display state never selects a backend route. The canonical behavior is
defined in the [tool-calling protocol](../ai-engineering/runtime/tool-calling-protocol.md).

## Data lifecycle

1. A channel supplies text, voice, or another source artifact through the API.
2. Source services preserve the raw input and channel metadata; media may
   produce a linked derived artifact such as a transcript.
3. Conversation entry invokes the configured application capability.
4. A known capability workflow prepares bounded context and invokes its states
   with typed DTOs, selected history, and model-safe references.
5. States use configured tools; deterministic services retrieve graph evidence,
   validate inputs, and perform allowed graph writes.
6. When useful, clarification pauses the originating state and resumes it by
   the normal matched tool-output continuation.
7. Graph writes preserve source/evidence relationships and trigger any approved
   indexing or asynchronous follow-up work.
8. Query capabilities retrieve, hydrate, and ground a response in memory and
   evidence for chat or graph rendering.

## Decisions to make during implementation

- Exact relational, vector, object-storage, queue, authentication, and secret
  service choices.
- Concrete provider/model routes behind the provider boundary.
- Exact API surface for graph/domain services.
- Backup, export, retention, and deletion behavior.
- Approval criteria for future profile, correction, and maintenance states.

## Related documentation

- [System architecture](system-architecture.md)
- [Deterministic agentic workflows](deterministic-agentic-workflows.md)
- [AI engineering](../ai-engineering/README.md)
- [External integrations](../external-integrations/README.md)
- [Graph model](../network/graph-model.md)
