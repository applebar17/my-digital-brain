# Wave 4 — application states and workflows

**Status: Not started**

## Outcome

Implement the concrete states under `product.application.states` and the
deterministic composition under `product.application.workflows`. Every state
has a functional input/output contract, prompt/context purpose, and explicit
toolbox. Data passed between states is documented at the domain meaning level.

## Issues

- [Issue 4.1 — conversation entry and memory query](issue-4.1-chat-and-memory-query/README.md)
- [Issue 4.2 — clarification as a state/tool interaction](issue-4.2-clarification-in-state-flow/README.md)
- [Issue 4.3 — memory-ingestion states and workflow](issue-4.3-memory-ingestion/README.md)
- [Issue 4.4 — other MVP application states](issue-4.4-other-mvp-states/README.md)

## Dependencies and boundaries

- Depends on Waves 2 and 3.
- State purposes and expected categories are indexed in the
  [application-state taxonomy](../../../ai-engineering/application-states/state-and-tool-taxonomy.md).
- Ingestion conventions and per-state prompt boundaries remain owned by the
  [ingestion specifications](../../../ai-engineering/application-states/ingestion/README.md)
  and [flow documentation](../../../flows/README.md).
- No fixed generic pipeline engine is introduced; the workflow is deterministic
  where already specified and uses explicit state handoffs.

## Exit evidence

- Chat/query and ingestion can run through concrete states with typed handoffs.
- When one state invokes another, its input and returned functional result are
  explicit; provider IDs remain inside the client protocol.
- Clarification is exercised through the normal child-state/tool interaction,
  not a separate architecture or runtime.
