# LLM Integration

## Role

LLMs are the main reasoning layer for extraction, clarification, summarization, and natural language interrogation. They help transform unstructured input into candidate graph changes, but they are not the source of truth.

## Core Uses

- Extract entities, relationships, claims, dates, places, and topics from sources.
- Detect missing information and propose clarification questions.
- Compare ambiguous entity candidates during resolution.
- Summarize entities, events, sources, and graph neighborhoods.
- Detect durable user traits and preferences for the personal profile memory flow.
- Convert natural language questions into retrieval plans.
- Generate grounded answers from retrieved graph evidence.
- Assist with media-derived text such as voice transcripts, OCR, and captions.

## Boundaries

The LLM should not directly write to the canonical graph. It should produce structured proposals that are validated before persistence.

Separate these stages:

- Prompt construction.
- Model call.
- Structured output parsing.
- Schema validation.
- Resolution and policy checks.
- Clarification.
- Graph write.

## Structured Outputs

LLM extraction should return a typed structure such as:

- Candidate entities.
- Candidate relationships.
- Candidate claims.
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

LLM extraction should produce structured ingestion objects, not graph database writes. The downstream pipeline owns validation, resolution, clarification, and persistence.

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

Open decisions:

- Use a single provider first or create a provider abstraction immediately.
- Use separate models for extraction, clarification, embeddings, and answer generation.
- Use a dedicated speech-to-text model for voice messages.
- Support local models for privacy-sensitive processing.
- Decide which data can be sent to external providers.
- Support both local-friendly and cloud-friendly model execution.

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
