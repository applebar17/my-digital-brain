# Issue 3.2 — define product tool DTOs and bindings

**Status: Not started**

Build the explicit product-level tool contracts that place deterministic
services or child states in a model's toolbox. Tool DTOs describe functional
intent and outputs, not storage internals or provider protocol.

## Tasks

- [Task 3.2.1 — define retrieval and graph tool bindings](task-3.2.1-read-and-write-tools.md)
- [Task 3.2.2 — define clarification interaction tool binding](task-3.2.2-clarification-tool-binding.md)

## Dependencies

- [Generic tool contract](../../wave-2-agentic-framework/issue-2.1-tool-contracts/README.md)
- Issue 3.1 deterministic services.
- [State and tool taxonomy](../../../../ai-engineering/application-states/state-and-tool-taxonomy.md)

## Functional communication DTOs

Tool inputs carry user/model intent and local references; outputs carry a
functional result, readable summary, relevant local refs, or an explanatory
error. For a child agent, the registered function translates its typed tool
input to a child state invocation and child result to one parent result.
