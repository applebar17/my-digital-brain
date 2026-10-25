# Wave 4 — workflow-first state slices

**Status: Not started**

## Outcome and execution method

Deliver a selected application workflow incrementally. First census its
agentic states and deterministic steps in execution order. Then complete one
state at a time: agree its functional behavior and inputs/outputs; define its
internal DTOs/artifacts and deterministic dependencies; define model-visible
tool contracts and map them to functions or child states where needed; wire its
handoff into the workflow; and verify the slice before advancing.

DTO and tool choices are made when the state requires them. Do not treat the
Wave 3 capability candidates or current application-state drafts as finalized
contracts.

## Issues

- [Issue 4.0 — first workflow and state census](issue-4.0-first-workflow-and-state-census/README.md)
- [Issue 4.1 — conversation entry and memory query](issue-4.1-chat-and-memory-query/README.md)
- [Issue 4.2 — clarification as a state/tool interaction](issue-4.2-clarification-in-state-flow/README.md)
- [Issue 4.3 — memory-ingestion states and workflow](issue-4.3-memory-ingestion/README.md)
- [Issue 4.4 — other MVP application states](issue-4.4-other-mvp-states/README.md)

## First workflow

Start with memory ingestion, whose deterministic handoff sequence is already
documented. Issue 4.0 validates that sequence and identifies which steps are
agentic states versus deterministic functions. Issue 4.3 then delivers the
confirmed states in order, pulling in only the Wave 3 capabilities each state
actually needs. The current issue/task breakdown is an initial map and may be
refined by the census before implementation.

## Dependencies and boundaries

- Depends on Wave 2. Wave 3 capabilities are introduced just in time by the
  state slices that require them, not completed wholesale in advance.
- State purposes and expected categories are indexed in the
  [application-state taxonomy](../../../ai-engineering/application-states/state-and-tool-taxonomy.md).
- Ingestion conventions and per-state prompt boundaries remain owned by the
  [ingestion specifications](../../../ai-engineering/application-states/ingestion/README.md)
  and [flow documentation](../../../flows/README.md).
- No fixed generic pipeline engine is introduced; the selected workflow uses
  explicit deterministic sequencing and state handoffs.

## Exit evidence

- Chat/query and ingestion can run through concrete states with typed handoffs.
- When one state invokes another, its input and returned functional result are
  explicit; provider IDs remain inside the client protocol.
- Clarification is exercised through the normal child-state/tool interaction,
  not a separate architecture or runtime.
