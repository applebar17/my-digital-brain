# LLM Integration

## Role

LLMs are the main reasoning layer for extraction, clarification, summarization, and natural language interrogation. They help transform unstructured input into candidate graph changes, but they are not the source of truth.

In the MVP, model behavior is coordinated by the AI Manager. The AI Manager can make dynamic conversational decisions and call tools, while graph writes remain validated through the Network API.

## Core Uses

- Extract entities, relationships, claims, dates, places, and topics from sources.
- Extract user-stated perceptions, emotional summaries, relationship contexts, and original user wording for any memory-bearing target when present.
- Detect missing information and propose clarification questions.
- Raise grounded contradiction doubts when retrieved graph context conflicts with proposed memory writes.
- Run a specialized contradiction judge over proposed writes and graph context when invoked.
- Compare ambiguous entity candidates during resolution.
- Summarize entities, events, sources, and graph neighborhoods.
- Detect durable user traits and preferences for the personal profile memory flow.
- Convert natural language questions into retrieval plans.
- Generate grounded answers from retrieved graph evidence.
- Assist with media-derived text such as voice transcripts, OCR, and captions.

## Boundaries

The LLM should not directly write to the canonical graph. It should produce structured proposals that are validated before persistence.

The conversational LLM chooses which high-level action to invoke and proposes parameters. Backend services validate parameters, own process state, and perform all persistence.

The approved top-level action surface is small:

- default answer path: no tool call
- `start_memory_ingestion`
- `query_memory_context`
- `propose_memory_correction`

Do not expose process-state operations such as resume, cancel, expire, validate write plan, or execute write plan as broad top-level tools. Those are backend orchestration details.

Separate these stages:

- Prompt construction.
- Model call.
- Structured output parsing.
- Cheap mention scan.
- Compact graph-context retrieval.
- Conversation history and pending process context attachment.
- Context-aware ingestion planning.
- Schema validation.
- Resolution and policy checks.
- Context review for contradiction suspicion.
- Contradiction judge invocation when the memory-writing agent has grounded doubt.
- Clarification or pending process resumption when appropriate.
- Graph write.

Clarification style and flow can be model-guided. Persistence is limited to pending process context and conversation history references so the AI Manager can resume the conversation after a later chat message from any consumer.

Pending state should enrich the next model or process call. It should not force a rigid deterministic route for the next message.

## Structured Outputs

LLM extraction should return a typed structure such as:

- Candidate entities.
- Candidate relationships.
- Candidate claims.
- Candidate perceptions.
- Candidate relationship contexts.
- Emotional summaries attached to entities, claims, sources, relationship contexts, or important relationships.
- Original user wording references.
- Candidate profile memories.
- Candidate metadata patches.
- Candidate enrichment requests.
- Mentioned time ranges.
- Mentioned places.
- Confidence scores.
- Missing fields.
- Ambiguity markers.
- Proposed clarification questions.
- Evidence spans or source references.
- Transcript confidence and uncertain spans when input comes from voice messages.

The exact schema should be versioned so previous extraction runs remain interpretable.

LLM extraction should produce structured ingestion drafts, not graph database
writes or backend records. The downstream pipeline enriches drafts with
deterministic IDs, source provenance, evidence refs, metadata, validation,
resolution, clarification, and persistence.

## Context-Aware Ingestion Planning

Ingestion complexity must be determined after the model sees relevant graph context, not from raw source text alone.

Required planning flow:

1. Run a cheap mention scan over source text or transcript.
2. Retrieve compact graph context for the mentions.
3. Ask the ingestion planner for an `ExtractionPlanDraft`.
4. Backend-enrich the draft into an `ExtractionPlan`.
5. Execute the selected backend flow.

Planner execution modes:

- `simple_single_pass`
- `focused_extraction`
- `needs_context_expansion`
- `needs_clarification_first`

The planner proposes extraction tasks. It does not plan graph writes.

Focused extraction should be used when a source contains affective content, relationship history, temporal nuance, multiple possible targets, or metadata-rich facts. This keeps model calls smaller and reduces hallucination risk.

## Personality And Profile Extraction

Some model outputs should be routed to a profile memory flow rather than directly into general graph memory. This applies when input reveals stable information about the owner of the brain, such as communication preferences, personality traits, recurring goals, work style, or privacy expectations.

Profile extraction should be conservative:

- Prefer explicit user statements over inference.
- Avoid turning temporary moods into traits.
- Mark sensitive traits as confirmation-required.
- Store evidence and confidence.
- Keep profile memory correctable and removable.

Approved profile memories can be retrieved during prompt construction, but they should not override the user's current instruction.

## Prompt Versioning

Prompts should be treated as product logic.

Track:

- Prompt name.
- Prompt version.
- Model name.
- Model provider.
- Output schema version.
- Runtime parameters.
- Source identifiers.

This makes extraction behavior debuggable and repeatable.

## Provider Strategy

Locked decisions:

- Use provider abstractions for LLM, structured generation, embeddings, speech-to-text, and model routing.
- Support OpenAI and Azure OpenAI behind the same ingestion-facing contracts.
- Use a dedicated speech-to-text capability for voice messages.
- Keep `ai/` as infrastructure. Memory extraction business logic lives in ingestion services.

Future decisions:

- Support local models for privacy-sensitive processing.
- Decide which data can be sent to external providers by privacy level.
- Add richer cost/latency routing after the MVP path is working.

## Validation

LLM output must be validated before use:

- Required fields are present.
- Entity and relationship types are allowed.
- Dates and locations are normalized where possible.
- Confidence is within expected range.
- Evidence references point to valid sources.
- Transcript-derived evidence points back to both transcript and original audio where possible.
- Graph writes do not violate identity rules.

Invalid output should be rejected, retried, or routed to a fallback prompt.

## Safety And Privacy

Because the graph contains personal memories, model calls should be explicit about:

- Which content is sent externally.
- Whether raw source content is sent or summarized first.
- Whether sensitive data is redacted.
- Whether voice audio or only the transcript is sent to external providers.
- Whether provider logs or retention settings apply.
- Whether a local processing mode is available.

## Evaluation

LLM behavior should be tested with example memories:

- Homonymous people.
- Vague locations.
- Approximate dates.
- Repeated events.
- Contradictory facts.
- User corrections.
- Media-derived transcripts.

Evaluation should measure extraction quality, clarification usefulness, duplicate prevention, and answer grounding.
