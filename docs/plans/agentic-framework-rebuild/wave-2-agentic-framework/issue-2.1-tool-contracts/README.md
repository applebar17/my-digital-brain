# Issue 2.1 — typed tool definitions and toolbox

**Status: Not started**

Define the generic, provider-neutral boundary that pairs a model-visible tool
description and input DTO with one typed handler. Its annotated return type is
the successful domain output. The client adapter renders the provider
declaration, wraps success or failure in the existing `ToolOutputDTO`, and
owns provider call IDs. Tool results have only success and error outcomes;
human-input pauses belong to state/session flow.

## Tasks

- [Task 2.1.1 — define typed tool and result contracts](task-2.1.1-tool-and-result-contracts.md)
- [Task 2.1.2 — compose and invoke typed toolboxes](task-2.1.2-toolbox-composition.md)

## Dependencies

- [Tool definition and toolbox contract](../../../../ai-engineering/contracts/tool-definition-and-toolbox.md)
- [Tool-calling protocol](../../../../ai-engineering/runtime/tool-calling-protocol.md)

## Functional communication DTOs

The input DTO represents only arguments the model may provide. A tool-specific
output DTO represents successful domain data and is the handler's annotated
return type. The client uses one provider-facing `ToolOutputDTO` for success or
error; no second generic result envelope or pending/retryable tool status is
introduced. Dependencies are bound at toolbox composition rather than passed
through a generic execution-context DTO.
