# AI Provider Foundation

## Goal

Shape `src/my_digital_brain/ai/` into a provider-neutral AI infrastructure package for LLM, embedding, tool, and speech-to-text integration.

This package must stay below application business logic. It should know how to call AI capabilities and normalize their outputs, but it should not know what a memory, entity, relationship, graph write plan, clarification, or ingestion session means.

## Locked Decisions

- `ai/` is infrastructure only.
- Memory extraction contracts live outside `ai/`, most likely under a future `ingestion/` package.
- Speech-to-text only converts audio into text plus metadata. The transcript is later ingested as a normal user message by the ingestion layer.
- Ingestion and chat code must depend on provider protocols, not directly on `GenAIClient`.
- Provider-neutral schemas may mimic OpenAI concepts where useful, but they should hide OpenAI versus Azure differences from callers.
- Provider request metadata should be returned by adapters first. Database persistence into `provider_request_logs` belongs to the caller or service layer.
- Prompt/schema version and privacy fields are optional metadata hooks for now, not policy engines.
- Keep the first implementation synchronous unless the Telegram/backend runtime forces async later.
- Keep the model router slim. It should provide task-to-model defaults, not a full cost/latency optimizer yet.

## Out Of Scope

- Memory extraction schemas such as `CandidateEntity`, `CandidateRelationship`, or `GraphWritePlan`.
- Telegram handling.
- Ingestion session state.
- Prompt registry persistence.
- Provider request log database writes.
- Cost accounting beyond optional metadata fields.
- Privacy enforcement logic.
- Async orchestration.

## Wave 1: Provider Contracts And Neutral Schemas

### Summary

Add the protocol and schema layer that future ingestion code will depend on. This wave should not change the current `GenAIClient` behavior except where small import or typing adjustments are needed.

### Files To Add

- `src/my_digital_brain/ai/protocols.py`
  - `LLMProvider`
  - `StructuredLLMProvider`
  - `EmbeddingProvider`
  - `SpeechToTextProvider`
  - `ModelRouter`

- `src/my_digital_brain/ai/schemas.py`
  - `AIRequestContext`
  - `ChatMessage`
  - `ChatRequest`
  - `ChatResult`
  - `StructuredGenerationRequest`
  - `StructuredGenerationResult`
  - `EmbeddingRequest`
  - `EmbeddingResult`
  - `TranscriptionRequest`
  - `TranscriptionResult`
  - `TranscriptionSegment`
  - `ProviderUsage`
  - `ProviderCallMetadata`
  - `ModelRoute`

- `src/my_digital_brain/ai/provider_errors.py`
  - `ProviderErrorCode`
  - `ProviderError`
  - `normalize_provider_exception`

- `src/my_digital_brain/ai/request_log.py`
  - `ProviderRequestLogPayload`
  - helper to create a normalized log payload from request context, model route, result metadata, usage, and provider error.

- `src/my_digital_brain/ai/providers/__init__.py`
  - public provider adapter exports.

- `src/my_digital_brain/ai/providers/fake.py`
  - `FakeLLMProvider`
  - `FakeEmbeddingProvider`
  - `FakeSpeechToTextProvider`

### Schema Notes

`AIRequestContext` should carry optional cross-cutting metadata:

- `purpose`
- `source_id`
- `conversation_id`
- `prompt_id`
- `prompt_version`
- `schema_id`
- `schema_version`
- `privacy_level`
- `metadata`

These fields should not enforce policy yet. They are there so ingestion can pass traceable context into provider calls from day one.

`TranscriptionRequest` should start with an `audio_path` field. Bytes or file-like inputs can be added later if needed.

`ProviderCallMetadata` should include:

- provider name
- model or deployment
- started/ended timestamps where available
- latency milliseconds
- request ID if returned by provider
- raw provider metadata as a small dict

### Test Plan

- Protocols are importable without constructing a provider.
- Neutral schemas validate minimal and rich payloads.
- Fake providers implement the protocols and return deterministic results.
- Provider error normalization maps common error shapes into stable error codes.
- Request-log payload helper produces a serializable dict.

## Wave 2: OpenAI/Azure Adapters, STT, And Slim Router

### Summary

Wrap the current `GenAIClient` behind the provider protocols and add speech-to-text support. Keep the adapter thin: it translates neutral request objects into low-level client calls and returns neutral result objects.

### Files To Add

- `src/my_digital_brain/ai/providers/openai.py`
  - `OpenAIProvider`
  - Implements:
    - `generate_chat`
    - `generate_structured`
    - `embed`
    - `transcribe`
  - Uses `GenAIClient` internally.

- `src/my_digital_brain/ai/providers/azure_openai.py`
  - `AzureOpenAIProvider`
  - Use this if Azure deployment naming creates enough difference to justify a separate adapter.
  - If not needed, document that `OpenAIProvider` can wrap Azure through `GenAISettings`.

- `src/my_digital_brain/ai/router.py`
  - `StaticModelRouter`
  - Task keys:
    - `default_chat`
    - `structured_extraction`
    - `summarization`
    - `embedding`
    - `speech_to_text`

### Files To Update

- `src/my_digital_brain/ai/client/core.py`
  - Add low-level `transcribe_audio(...)` or equivalent.
  - Keep it provider-specific and simple.

- `src/my_digital_brain/ai/client/settings.py`
  - Add speech-to-text model settings:
    - `openai_transcription_model`
    - `azure_openai_transcription_deployment`
  - Add default router model settings only where needed.

- `src/my_digital_brain/config.py`
  - Optional: expose AI provider settings through app settings if the application should configure providers centrally.

- `.env.example`
  - Add OpenAI/Azure AI settings needed for local configuration.

### Speech-To-Text Behavior

The provider should:

- accept local `audio_path`
- call the configured transcription model
- return normalized transcript text
- return optional language, duration, and segments if available
- include provider/model metadata
- avoid ingestion decisions
- avoid deleting, moving, or mutating the audio source

### Router Behavior

The first router should be deterministic and configuration-driven.

It should answer questions like:

- which provider handles `structured_extraction`?
- which model handles `summarization`?
- which model handles `speech_to_text`?

It should not estimate cost, inspect privacy policies, or dynamically optimize latency in this wave.

### Test Plan

- OpenAI provider can be instantiated with a fake or stubbed `GenAIClient`.
- Structured generation adapter returns a `StructuredGenerationResult`.
- Embedding adapter returns an `EmbeddingResult`.
- STT adapter returns a `TranscriptionResult`.
- Router returns expected default routes.
- Azure route/deployment settings resolve without changing ingestion-facing code.
- Provider errors become normalized `ProviderError` objects.
- Full pytest suite remains green without real external API calls.

## Open Questions

- Should Azure be a separate adapter class from the start, or should one `OpenAIProvider` handle both OpenAI and Azure through `GenAISettings`?
  - Current preference: separate classes only if deployment naming or API behavior makes the common adapter awkward.
- Should `TranscriptionRequest` support bytes/file-like inputs in v1?
  - Current preference: start with `audio_path` only.
- Should provider request logs be persisted by the adapter?
  - Current preference: no. Return metadata and let the caller persist it.

## Completion Criteria

- Ingestion code can use provider protocols without importing `GenAIClient`.
- Text generation, structured generation, embeddings, and transcription all have neutral request/result objects.
- OpenAI/Azure implementation details are hidden behind adapters.
- Fake providers allow ingestion tests without real provider calls.
- SearXNG remains the only built-in AI tool for now.
