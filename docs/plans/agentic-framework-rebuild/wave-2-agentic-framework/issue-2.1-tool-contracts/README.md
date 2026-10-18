# Issue 2.1 — typed tool definitions and toolbox

**Status: Not started**

Define the generic, provider-neutral boundary that pairs a model-visible tool
description and typed input/output with one executable handler. The client
adapter renders the provider declaration and owns provider call IDs.

## Tasks

- [Task 2.1.1 — define typed tool and result contracts](task-2.1.1-tool-and-result-contracts.md)
- [Task 2.1.2 — compose and invoke typed toolboxes](task-2.1.2-toolbox-composition.md)

## Dependencies

- [Tool definition and toolbox contract](../../../../ai-engineering/contracts/tool-definition-and-toolbox.md)
- [Tool-calling protocol](../../../../ai-engineering/runtime/tool-calling-protocol.md)

## Functional communication DTOs

Tool input DTO represents only the arguments the model is allowed to provide.
Tool output DTO represents the useful domain result or an error/recoverable
error. The registered handler receives an explicit execution context and input
DTO; the client wraps the result in the one provider-matched tool output.
