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

The clarification state may configure the question as a free response,
confirmation, or multiple choice. These are the complete MVP presentation
categories, not separate reasoning paths. Ordinary variations such as dates,
places, people, corrected choices, or natural-language details are handled by
the LLM using the question and answer content.

Correlation has three distinct owners:

- the invoking LLM creates a descriptive `clarification_ref` for the logical
  doubt and keeps it stable if that doubt is asked again;
- the backend creates a new `interaction_ref` for each concrete pending UI
  interaction;
- the provider creates the tool-call ID, which remains owned by the AI client
  and is used to pair the tool output with its call.

Clarification is plugged into ingestion/query/etc. through the ordinary typed
toolbox. It is not an independent frontend wave.

The question tool follows the shared [user-interaction tool contract](../../../../ai-engineering/application-states/user-interaction-tools.md)
for backend-owned deadline and answer/timeout resolution.
