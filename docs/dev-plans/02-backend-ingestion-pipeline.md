# Backend Ingestion Pipeline Definition

## Goal

Define the backend pipeline that turns Telegram text and voice inputs into graph updates, including both node and edge creation.

## Wave 0: Baseline Decisions

- Use Python for backend unless a strong reason appears otherwise.
- Use Pydantic objects for structured extraction and graph write plans.
- Keep the AI Manager dynamic and agentic.
- Keep graph writes validated through the Network API.
- Store raw sources before model processing.
- Treat voice transcripts as derived source artifacts linked to original audio.
- Integrate LLM and speech-to-text providers through an abstract, protocolled provider layer.
- Support OpenAI and/or Azure OpenAI behind the provider abstraction rather than coupling ingestion logic to one vendor.

## Wave 1: MVP Ingestion Loop

Implement the core path:

1. Receive Telegram text or voice input.
2. Store raw source.
3. Transcribe voice input if needed.
4. Select the configured model provider and model for the ingestion task.
5. Build context for extraction.
6. Extract candidate entities, relationships, claims, profile memories, and metadata patches.
7. Run basic validation.
8. Resolve obvious entity matches.
9. Ask clarification only when useful.
10. Write validated graph changes.
11. Return concise ingestion result.

Required structured objects:

- `SourceRecord`
- `ExtractionRun`
- `CandidateEntity`
- `CandidateRelationship`
- `CandidateClaim`
- `CandidateMetadataPatch`
- `ClarificationRequest`
- `ResolutionDecision`
- `GraphWritePlan`

Required provider abstractions:

- `LLMProvider`
- `SpeechToTextProvider`
- `EmbeddingProvider`
- `VectorStore`
- `ModelRouter`
- `ProviderRequestLog`

Provider abstractions should hide OpenAI versus Azure OpenAI differences from the ingestion pipeline. The vector store abstraction should support Chroma locally and Azure AI services in cloud mode.

## Wave 2: Resolution And Contradiction Handling

- Add richer entity resolution using aliases, embeddings, source context, temporal context, and existing graph neighborhoods.
- Detect likely duplicate people, places, events, and organizations.
- Detect contradictions during ingestion.
- Ask Telegram clarification when contradictions matter.
- Expire or dispute older facts when a new fact clearly supersedes them.
- Preserve both facts when ambiguity remains.

## Wave 3: Advanced Ingestion

- Batch reprocessing of sources when prompts or schemas improve.
- Provider/model routing by task difficulty, privacy level, latency budget, and cost budget.
- Extraction evaluation set using personal synthetic examples.
- Multi-source ingestion from documents, images, links, and calendar exports.
- Automatic enrichment requests for places or contacts when useful.
- Background maintenance scans for duplicates, stale facts, and weak metadata.

## Guardrails

- The LLM never writes directly to the graph.
- Graph write plans must validate before persistence.
- Sensitive facts require privacy-aware handling.
- Pending ingestion sessions expire.
- Tool-call loops have limits.
- Every persisted fact has source provenance.
- Provider calls are logged with model, prompt/schema version, latency, cost estimate where available, and privacy level.

## Initial Success Criteria

- Text memories can create nodes and relationships.
- Voice memories can be transcribed and ingested.
- OpenAI or Azure OpenAI can be swapped through configuration without changing ingestion logic.
- Chroma or Azure AI services can be swapped through the vector store protocol without changing ingestion logic.
- Ambiguous person/place references can trigger a clarification.
- Graph writes are auditable.
- Reprocessing a source does not create duplicate graph pollution.
