# Chat activity and clarification rendering

## Purpose

Chat communicates useful, user-understandable progress while work is running,
without exposing implementation IDs, internal state names, model reasoning, or
raw tool output as conversation text.

## Activity behavior

The backend maps a workflow/state activity to a user-facing category, a brief
title, and an optional factual summary. Titles may vary between occurrences but
remain stable for the same occurrence across polling, refresh, or navigation.

Activity events are operational UI data, not assistant messages and not model
history. The final chat transcript renders only the final assistant reply after
the entry state has received its confirmed tool outcome.

The UI can show concise phases such as understanding the request, finding
relevant memories, organizing information, saving confirmed details, or
checking consistency. Unknown future activities use a safe generic phrase; the
internal key remains available only to developer diagnostics.

## Clarification behavior

Awaiting clarification is a first-class interaction state, not a generic error
or indefinite loading state. The channel renders the structured question packet
and accepts supported text, selections, or audio. It does not render
`clarification_ref`, provider call IDs, backend IDs, raw validation errors, or
agent/tool transcripts.

After submission, the UI shows that the answer is being used and follows the
resumed originating state. It does not treat the question packet or a nested
tool output as a completed assistant response.

## Boundaries

- The frontend renders resolved activity and clarification data; it does not
  infer process state from assistant text or trace logs.
- The backend owns mapping from workflow/state events to the display model.
- The agentic runtime owns continuation and tool-call pairing.
- Developer trace views may expose sanitized technical diagnostics separately
  from normal chat UX.

## Verification

Test a normal completed ingestion, a refresh during work, a clarification
pause/resume, a recoverable tool failure, and a final response after a nested
tool. In each case, normal chat must contain no technical IDs or nested tool
prose.
