# Temporal Model

## Purpose

Personal memory depends heavily on time, but user input is often vague. The system must represent exact dates, fuzzy dates, source timestamps, and the time range during which a fact was true.

## Time Dimensions

### Event Time

When something happened.

Examples:

- A dinner happened on 2026-05-20.
- A trip happened in summer 2024.
- A meeting happened yesterday.

### Valid Time

When a fact was true.

Examples:

- Luca worked at a company from 2022 to 2024.
- A phone number was valid until March 2025.
- A preference was true at the time it was stated.

### Observed Time

When the system learned or observed the fact.

Example:

- The user said today that Luca changed job last year.

### Source Time

When the source artifact was created.

Examples:

- Telegram message timestamp.
- Photo EXIF timestamp.
- Document creation date.
- Calendar event date.

### Ingestion Time

When the system processed the source.

This matters for debugging and replaying ingestion.

## Precision

Time values should support precision:

- exact
- day
- month
- year
- season
- period
- range
- unknown

The original expression should be preserved when useful.

Example:

```json
{
  "original_time_text": "last summer",
  "resolved_start": "2025-06-01",
  "resolved_end": "2025-09-30",
  "time_precision": "season",
  "time_basis": "conversation_at",
  "timezone": "Europe/Rome"
}
```

Do not store model-generated numeric confidence for temporal inference in the first version. LLMs can help infer dates, but fake precision is dangerous. Store the basis and precision of the resolution instead.

## Relative Time

Relative expressions such as "yesterday", "last week", and "two years ago" must be resolved against the source time, not the ingestion time, when possible.

If a source was written on 2026-05-24 and says "yesterday", the event date should resolve to 2026-05-23.

If a user sends a live chat message, the conversation timestamp is a valid resolution basis. The LLM or temporal inference pipeline should know the current interaction time, user timezone, source timestamp, and previous conversation context.

## Dedicated Temporal Inference

Uncertain dates should eventually go through a dedicated temporal inference pipeline. That pipeline can use:

- conversation timestamp
- source timestamp
- user timezone
- previous messages in the ingestion session
- known events or periods in the graph
- external metadata when available

The pipeline output should still be deterministic graph fields: `original_time_text`, `resolved_start`, `resolved_end`, `time_precision`, `time_basis`, and `timezone`.

## Contradictions Over Time

Some apparent contradictions are valid temporal changes.

Example:

- "Giulia lives in Rome."
- Later: "Giulia moved to Milan."

This should become a temporal update, not necessarily a contradiction. The previous fact can be expired and the new fact marked current.

## Query Behavior

The query layer should support:

- "current" facts by default.
- Historical facts when explicitly requested.
- Fuzzy date filtering.
- Timeline views.
- Sorting memories by event time, source time, or ingestion time.

Answers should distinguish:

- "This happened in 2024."
- "You told me this in 2024."
- "This was true around 2024."
