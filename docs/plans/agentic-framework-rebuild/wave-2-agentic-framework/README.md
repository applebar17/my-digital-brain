# Wave 2 — generic agentic framework

**Status: Not started**

## Outcome

Build the reusable framework in `product.agentic`, on top of
`product.ai.ai_clients`. It owns state-local invocation and history lifecycle,
not product-specific prompts, graph policy, clarification policy, or workflow
sequencing.

## Issues

- [Issue 2.1 — typed tool definitions and toolbox](issue-2.1-tool-contracts/README.md)
- [Issue 2.2 — shared history session](issue-2.2-history-session/README.md)
- [Issue 2.3 — base agentic state and preparation](issue-2.3-base-state-and-preparation/README.md)

## Dependencies and boundaries

- Depends on Wave 1 client adoption and verification.
- Source of truth: [AI contracts](../../../ai-engineering/contracts/README.md)
  and [AI runtime](../../../ai-engineering/runtime/README.md).
- Generic tests may use small fake states/tools; product workflows are not
  introduced in this wave.

## Exit evidence

- A state can be invoked directly or as a typed mapped tool using the same
  entrypoint.
- Child state output returns as one matched parent tool result through the
  client loop.
- History and optional preparation behavior match their specifications.
