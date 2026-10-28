# Task 4.3.1 — define ingestion request and reasoning context

**Status: Ready for review**

## User story

As the conversation-entry state, I want ingestion to inherit my selected
history and current user message, so the ingestion reasoning state interprets
the original conversation instead of model-regenerated memory content.

## What and why

Define the workflow entry DTO, deterministic context preparation, and
`IngestionReasoningState`. The `ingest_memory` model-facing input contains only
optional purpose guidance such as “store the memory about the barbecue.” The
actual source remains the exact inherited history projection established by
Tasks 4.3.0a–4.3.0b.

Deterministic preparation registers the dynamic owner projection, reuses the
run's `ReferenceContext`, and may retrieve bounded owner-scoped memory context.
It does not copy conversation content into another source DTO, interpret the
memory, propose objects, or plan writes.

`IngestionReasoningState` is one structured main LLM call with no separate
framework reasoning/planning stage and no default toolbox. Its implementation
slice is primarily its explicit input/output DTOs, versioned prompt, effective
toolbox configuration, and workflow step.

## Where

- `src/product/application/states/ingestion/reasoning/` models and state.
- Versioned ingestion-reasoning prompt.
- Memory-ingestion workflow entry and preparation step.
- Owner and reference rendering per the canonical context specification.

## Functional communication boundary

Tool input: optional ingestion guidance only. Framework context: inherited
caller history containing the current user message, plus the shared history
session and parent linkage. State context: owner projection, rendered relevant
references, and bounded retrieved memory context. State result:
`IngestionReasoningResultDTO`, whose primary `clarification_points` field
carries unclear, incomplete, contradictory, or incoherent user statements and
why they may matter. Summary, entity, alias, relationship, and episodic
observations remain simple supporting lists. The owner shown to the model is a
functional identity projection, not the backend owner UUID.

## Dependencies and acceptance

- Depends on Tasks 4.3.0a–4.3.0b and follows the approved Task 4.0.1 inventory.
- Add a Wave 3 service/tool dependency only when the agreed state behavior
  requires it.
- Owner context is derived per invocation, never hard-coded or stale.
- Reasoning receives inherited history and typed context, not regenerated
  source content or only an isolated goal string.
- The prompt and Pydantic field descriptions are the coherent behavior/output
  contract; no write-tool schema is introduced in this task.
- No proposed action or reasoning artifact is mistaken for a completed write.
