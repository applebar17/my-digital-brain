# Local workflow inspector

## Purpose

Provide a developer-only, read-only view of the workflow that the application
actually assembles and of a selected run through that workflow. The viewer
helps a human see what each step does, what it received and returned, which
tools were available, and where a run stopped or failed. It is a debugging
surface, not a workflow editor or a second source of configuration.

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

## Two views of the same workflow

1. **Composition view:** Show the ordered graph of agentic states and
   deterministic steps, their dependencies, concise descriptions, and the
   functional input/output contract on each handoff. Selecting an agentic
   state shows its configured reasoning and planning stages, main-call purpose,
   versioned prompt template, toolbox, and each tool's description and
   annotated input/output DTO fields and descriptions. The state panel also
   shows its own invocation/result DTO fields. Show the configuration actually
   assembled for that workflow; where a toolbox is narrowed per invocation,
   show the effective selection for the chosen run as well. An agentic tool
   that invokes a child state appears as a link to that state's configuration.
   For example, clarification appears as a child AI state whose toolbox
   contains the deterministic UI interaction tool.
2. **Run view:** Select a local run or conversation and highlight its actual
   path through the same graph. Show the current or last reached step,
   completed steps, failures, clarification waits, and the typed input/output
   values at each step, plus the resolved prompt snapshot used by that run.
   Show tool invocations and their outcomes under the owning agentic state.
   A child-state invocation opens a nested run path:
   the parent waits for the child result, the child can wait for user input,
   and the typed child result returns as the parent's matched tool output.
   The developer may open the existing detailed AI trace for provider-level
   diagnosis.

The diagram must distinguish AI-backed states from deterministic steps. Labels
use functional names first; technical DTO and tool names are available in the
detail panel. A failed tool call remains visible in the state that invoked it,
including the returned error output and any later recovery.

## Source of inspection data

- Composition data comes from the step declarations in the assembled
  `BaseWorkflow` subclass and from the actual state/toolbox objects it holds.
  Those same step declarations drive dependency execution. Do not maintain a
  second handwritten workflow graph, shadow tool registry, or editor-specific
  configuration.
- Each step exposes an inspection description of its purpose, kind, input/output
  DTOs from annotated callables, and dependency links. Agentic state
  inspection includes configured reasoning/planning stages and their artifact
  contracts, main call, prompt identity, and registered tools.
  Runtime-selected toolboxes are reported from that invocation, not inferred
  from a static maximum set.
- Runtime data comes from the same state, workflow, and tool execution
  boundaries used by the application, linked by a run identifier and step
  identity. The UI is a projection of those records; it does not infer progress
  from assistant prose or raw provider messages.
- Show typed payloads, resolved prompt snapshots, and errors after the same
  redaction rules used for developer traces. Keep raw provider exchanges in
  the existing trace detail.

The first implementation can use a simple read-only graph/list and detail
panel within the existing developer trace page. No drag-and-drop editing,
general workflow DSL, or new product-facing chat status contract is required.
The surface is available only in local/development mode through the existing
developer access boundary.

## Minimum useful scenario

Open the local inspector, choose the memory-ingestion workflow, and see its
declared states and deterministic steps. Start an ingestion from chat, select
that run, and watch its path advance. Open a state to compare its configured
toolbox and input/output contract with the actual typed input, tool outputs,
and result. If clarification or a tool error occurs, see the parent state, the
child clarification state, its UI interaction, and whether the parent later
resumes or recovers.
