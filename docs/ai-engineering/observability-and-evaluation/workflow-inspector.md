# Local workflow inspector

## Purpose

Provide a developer-only, read-only view of the workflow that the application
actually assembles. The first deliverable is a standalone local Python server
and HTML page, not an application frontend route. It shows step dependencies,
configured agentic calls, prompts, toolboxes, and annotated DTO fields. It is
not a workflow editor or a second source of configuration.

The functional ingestion sequence and its handoffs are defined in the
[memory-ingestion workflow map](../../architecture/memory-ingestion-workflow-map.md).
The generic workflow base is specified in
[deterministic agentic workflows](../../architecture/deterministic-agentic-workflows.md).
The inspector reads the step composition exposed by `BaseWorkflow` and the
actual configuration of each referenced state and toolbox. The concrete
`MemoryIngestionWorkflow` inherits the base; its `ingest_memory` method is the
handler for the chatbot's tool of the same name.

The [agentic state framework](../runtime/agentic-state-framework.md) owns state
invocation; [tool definitions](../contracts/tool-definition-and-toolbox.md)
own model-visible tool descriptions and typed handler contracts. This document
owns only their inspection surface.

## First deliverable: assembled configuration

Show the ordered graph of agentic states and deterministic steps, their
dependencies, descriptions, and annotated input/output DTO fields. Selecting
an agentic state shows its configured main call, optional reasoning/planning
calls, current system prompt text, toolbox, and tool input/output contracts.
Read the actual assembled step and state configuration; do not maintain a
second handwritten graph. A clearly marked sample composition is acceptable
until the first product workflow exists. Prompt identity/version is omitted
until versioned prompts are supported by the runtime.

The local page distinguishes AI-backed states from deterministic steps. Labels
use functional names first; technical DTO and tool names are available on
selection. The server binds only to loopback and receives the assembled
workflow object from its caller. It does not import the old trace store or
require the application frontend.

## Later: selected-run overlay

When actual states and their runtime boundaries are wired, a later slice may
overlay a selected run on this composition: completed/waiting/failed steps,
typed values, tool outcomes, nested clarification, effective per-run toolbox,
and resolved prompt. That slice must use the runtime's real events and
redaction rules. Do not add a parallel trace store, infer progress from
provider prose, or build this overlay as part of the first deliverable.

No drag-and-drop editor, general workflow DSL, new product-facing chat status
contract, or integration into the existing developer trace page is required.

## Minimum useful scenario

Start the local inspector with the clearly marked sample workflow and inspect
its deterministic and agentic steps. Select the agentic step to see its main
prompt, optional reasoning call, toolbox, and input/output DTO fields. When
`MemoryIngestionWorkflow` is later assembled, pass that same object to the
server; the inspector uses its declared steps rather than a duplicate diagram.

From this repository on Windows, launch the sample locally without the
application frontend or a PowerShell script:

```powershell
cd src
..\.venv\Scripts\python.exe -m product.dev.workflow_inspector
```

Open `http://127.0.0.1:8765` and stop the server with Ctrl+C.
