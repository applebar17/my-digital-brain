# Tools that request user input

## Purpose

This contract applies only to mapped tools whose function is to request a
user-visible interaction and wait for that user's response. It does not add
timeouts or pause behavior to ordinary tools.

## Ownership and lifecycle

The backend interaction service owns the pending interaction and its deadline.
The UI renders the question and submits the answer; any frontend countdown is
informational and does not decide whether an answer is timely.

```text
UI-interaction tool creates question and deadline
  -> backend persists the minimum continuation and returns the pending question
  -> user answers before deadline OR backend deadline expires
  -> backend supplies exactly one answer-or-timeout result to the waiting tool call
  -> the tool batch is complete and the model session continues
```

The timeout is configured for the UI-interaction tool/request. Its clock starts
when the backend creates the pending interaction. The exact duration and
default are selected by the implementing interaction contract; this document
does not impose one global timeout on tools.

Persist only the correlation and state continuation needed to resolve the
pending interaction: the interaction reference, deadline, waiting state/tool
call linkage, and the question packet required by the UI. Do not persist
reasoning/planning artifacts as part of this mechanism.

An answer and timeout race to resolve the same pending interaction. The backend
accepts only the first valid resolution, then supplies one result matched to
the original provider call ID. For a parallel tool-call batch, completed
sibling outputs remain held until every call has an output; the model receives
the complete batch once.

## Boundaries

- The client/runtime owns provider transcript pairing and batch completion.
- The backend interaction boundary owns persistence, deadline enforcement, and
  answer/timeout resolution.
- The frontend owns presentation and answer submission, not timeout authority.
- The timeout is an expected tool result to the model, not a pipeline-breaking
  condition or a new general tool status.

The generic tool protocol is defined in
[tool-calling protocol](../runtime/tool-calling-protocol.md). This document
defines only the application behavior for tools that wait on a human response.
