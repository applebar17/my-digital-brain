# Issue 4.2 — clarification as a state/tool interaction

**Status: Not started**

Implement the clarification agent and its interaction with the existing
human-answer channel as part of the states that need it. This issue exists to
deliver the concrete behavior and functional contract; pause/resume mechanics
remain generic framework behavior from Wave 2.

## Tasks

- [Task 4.2.1 — define clarification request/result and implement the child state](task-4.2.1-clarification-state.md)
- [Task 4.2.2 — connect question and answer to the invoking state](task-4.2.2-clarification-handoff.md)

## Dependencies

- [Interrogation flow](../../../../flows/interrogation.md)
- [Clarification agent state inventory](../../wave-0-census/issue-0.3-integration-census/chat-and-clarification-file-census.md)
- Issues 2.2, 3.1, and 3.2.

## Functional communication DTOs

The caller sends the goal, relevant context, and identified uncertainty. The
clarification state returns a human-language question/interaction request and,
after the answer, a resolved answer packet to its caller. Any internal
`clarification_ref` correlates that business question; provider call IDs are
separate protocol metadata.

Clarification is plugged into ingestion/query/etc. through the ordinary typed
toolbox. It is not an independent frontend wave.
