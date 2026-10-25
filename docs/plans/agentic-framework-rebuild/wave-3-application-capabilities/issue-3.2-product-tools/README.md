# Issue 3.2 — define product tool DTOs and bindings

**Status: Deferred until an agreed state requires a model-visible tool**

This issue is a just-in-time backlog, not a prerequisite tool inventory. Define
each product-level tool only after its consuming state has an agreed functional
need. Its DTO describes that intent and output, not storage internals or
provider protocol. The generic tool framework itself is already established in
Wave 2.

## Tasks

- [Task 3.2.1 — define retrieval and graph tool bindings](task-3.2.1-read-and-write-tools.md)
- [Task 3.2.2 — define clarification interaction tool binding](task-3.2.2-clarification-tool-binding.md)

## Dependencies

- [Generic tool contract](../../wave-2-agentic-framework/issue-2.1-tool-contracts/README.md)
- Issue 3.1 deterministic services.
- [State and tool taxonomy](../../../../ai-engineering/application-states/state-and-tool-taxonomy.md)

## Candidate communication contracts (non-binding)

When a state requires a tool, its inputs may carry user/model intent and local references; outputs may carry a
functional result, readable summary, relevant local refs, or an explanatory
error. For a child agent, the registered function translates its typed tool
input to a child state invocation and child result to one parent result.
These are design constraints, not a declaration that every candidate tool or
field is needed.
