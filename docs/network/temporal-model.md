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

- exact datetime
- date
- month
- season
- year
- range
- relative expression
- unknown

The original expression should be preserved when useful.

Example:

```json
{
  "original_text": "last summer",
  "normalized_range": {
    "start": "2025-06-01",
    "end": "2025-09-30"
  },
  "precision": "season",
  "confidence": 0.72
}
```

## Relative Time

Relative expressions such as "yesterday", "last week", and "two years ago" must be resolved against the source time, not the ingestion time, when possible.

If a source was written on 2026-05-24 and says "yesterday", the event date should resolve to 2026-05-23.

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
