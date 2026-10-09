# Chat Workspace Requirements

## Purpose

Web chat is a first-class interface to the conversation capability shared with
other supported channels. It lets the owner capture memories, ask about stored
information, request corrections, and answer clarification questions.

## Layout and interaction

The chat workspace provides:

- a conversation timeline and text composer;
- a concise session header and user-understandable activity while work is in
  progress;
- structured clarification questions when the application needs an answer;
- a clear final assistant response after the invoked work returns;
- access to evidence referenced by an answer; and
- loading, request-failure, and accepted-background-work feedback.

Attachment and audio input may be added as the corresponding application
capabilities become available. Diagnostics are hidden in normal use and belong
in a separate developer experience.

## Activity and final response

Activity is a display of meaningful progress, not a second conversation. It is
operational UI data, separate from assistant messages and model history. It
must not expose internal reasoning, state names, tool transcripts, provider
details, or technical identifiers.

The backend maps supported workflow activity to a user-facing category, brief
title, and optional factual summary. A title remains stable for the same active
work across polling, refresh, or navigation. Unknown activities use a safe
general phrase; their internal keys remain developer-only.

Examples of understandable phases include understanding the request, finding
relevant memories, organizing information, saving confirmed details, and
checking consistency. The final transcript shows the final assistant response,
not a nested tool result or progress event.

## Clarification interaction

Clarification appears as a structured interaction in the current conversation,
not as a completed assistant response or an opaque loading state. The owner can
answer through the available response controls and may provide free text when
suggested choices do not fit.

After submission, the chat indicates that the answer is being used and reflects
the resumed work. The frontend does not infer whether arbitrary text should
resume a clarification; only an answer associated with the displayed
interaction is submitted as its response.

Do not render clarification references, provider call IDs, database IDs, raw
validation errors, or agent/tool transcripts as chat text. See the [functional
clarification requirements](../functional/clarification-agent-and-ux.md) for
question behavior and answer expectations.

## Evidence navigation

When an answer includes evidence, the owner can inspect a source summary and
navigate to related graph context. Where available, evidence distinguishes
user-stated, inferred, externally enriched, contradicted, and stale
information. A proposed mutation requires clear confirmation before it is
applied.

## Ownership boundaries

- The frontend renders activity and clarification data; it does not infer
  process state from assistant prose or developer traces.
- Backend/application contracts provide user-safe activity, final content, and
  clarification interaction data.
- Runtime continuation and provider tool-call pairing are owned by [AI
  engineering](../../ai-engineering/README.md).
- The chat does not display technical diagnostics by default.

## Acceptance checks

Verify a completed ingestion, refresh during active work, clarification
pause/resume, recoverable failure, and final response after a nested tool. The
normal chat transcript must show no technical IDs or raw nested tool prose.
