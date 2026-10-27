# Deterministic agentic workflows

## Purpose

A deterministic agentic workflow coordinates a known sequence of agentic
states for one application capability. It is deterministic about execution
order, dependency handoff, and context propagation. It is not deterministic
about the semantic judgments made inside an LLM state.

This is the MVP orchestration approach. A future agent-to-agent coordinator may
replace the workflow scheduler, but it must preserve the same state entrypoints,
DTO contracts, tool protocol, history behavior, and reference-context boundary.

## Workflow responsibility

`BaseWorkflow` is the small shared base for workflow composition and execution.
`MemoryIngestionWorkflow(BaseWorkflow)` supplies the concrete ingestion steps
and an annotated `ingest_memory` entrypoint. The chatbot's `ingest_memory` tool
is registered against that bound method. Its validated request enters the
workflow; the workflow's compact typed result returns as the matched tool
output to the chat-facing agent, which resumes and writes the final reply.
The application binds the active owner, selected history, and service
dependencies when assembling the workflow/toolbox; the model-visible tool
request carries only the fields the chatbot needs to provide.
For `ingest_memory`, that request carries only optional ingestion guidance.
The current message and selected conversation turns reach the workflow through
the framework-owned parent invocation context; the conversation model does not
regenerate the memory source as tool arguments.

The base invokes the concrete workflow's configured steps in dependency order,
passes typed compact outputs to dependent steps, and exposes that same assembled
composition for the local inspector. One step declaration supplies its
functional name, kind, callable state/function, and dependency links. The
inspector derives input/output DTO fields from the callable's annotations and
reads the actual state/toolbox configurations; it does not keep another
diagram definition.
Conceptually, the chatbot's registered `ingest_memory` handler is the bound
`MemoryIngestionWorkflow.ingest_memory` method, which delegates to the base's
execution of those configured steps. The exact request/result DTO names are
confirmed with the concrete ingestion workflow task.
The workflow owns:

- the workflow input and final-result DTOs;
- declared state order and input/output dependencies;
- deliberately approved parallel work where sibling states have no data
  dependency;
- the selected history projection, evolving `ReferenceContext`, and compact
  prior-state results provided to each state;
- waiting for a state's completed result before advancing its dependent steps,
  including when the agentic runtime resumes that state after clarification.

Independent sibling steps can appear side by side in the inspector. The first
base executes declared steps in order; actual parallel execution would need an
explicit later decision and still wait for all required results. The base does
not decide independence from a drawing or from LLM output.

It does not interpret LLM output, perform graph writes, infer missing graph
objects, parse prose into DTO fields, hide tool failures, or carry raw provider
traces between states.

The workflow does not create a second source-history DTO. Its AI states inherit
the invoker's selected conversational projection through
`AgenticHistorySession`; state-specific semantic handoffs remain explicit DTOs.

## State handoff contract

Every workflow state receives a typed input DTO and returns a typed compact
result DTO. The result contains only the semantic output required by a
dependent state, plus an optional typed reference-context delta. Raw history,
provider responses, tool-call identifiers, and backend identifiers stay with
their owning runtime/service boundaries.

```text
workflow input + selected history + ReferenceContext
  -> state input DTO
  -> agentic state / deterministic service
  -> compact state result DTO + ReferenceContext delta
  -> next dependent state input DTO
```

The workflow merges a valid reference delta before preparing the next state.
It does not create a second alias convention or expose private mappings.

## Memory-ingestion workflow map

The [canonical diagram and step descriptions](memory-ingestion-workflow-map.md)
show the concrete ingestion sequence and its clarification branch. The generic
workflow contract above governs that composition.

## Clarification and errors

When a parent state invokes clarification, its provider tool call awaits the
child `ClarificationAgentState`. The child waits on its deterministic UI tool;
the user answer or timeout becomes that child tool call's matched output. After
the child completes, its typed result becomes the single matched output for
the parent's original agentic tool call. The parent resumes with its preserved
history, typed context, and reference context. The workflow continues after
the parent completes; it does not reroute the request to another workflow step.

If a deterministic tool or child state fails, the caller receives one compact,
actionable tool output and may respond, retry with corrected DTO arguments, ask
clarification, or return a partial semantic result. The workflow receives the
eventual state result; it must not turn the tool result itself into a user-facing
chat answer or terminate the caller chain.

## Parallelism

Parallel execution is allowed only where a workflow definition explicitly
declares sibling tasks context-independent. A task that creates or resolves a
reference required by another task is sequential by definition. The initial
ingestion workflow therefore preserves node, memory/context, and relationship
dependencies. It makes no premature promise to parallelize those states.

## Future replacement boundary

If the product later adopts agent-to-agent delegation, only the coordination
policy changes. Each state still exposes the same `BaseAgenticState` entrypoint,
accepts typed input/context, uses its configured toolbox, and returns a compact
result. The new coordinator must obey the same history, reference, tool-output,
and error-continuity contracts.

## Related documentation

- [Memory-ingestion workflow map](memory-ingestion-workflow-map.md)
- [System architecture](system-architecture.md)
- [Agentic state framework](../ai-engineering/runtime/agentic-state-framework.md)
- [Agentic history session](../ai-engineering/runtime/agentic-history-session.md)
- [Tool-calling protocol](../ai-engineering/runtime/tool-calling-protocol.md)
- [Reference context and owner projection](../ai-engineering/context-and-prompts/reference-context-and-owner-projection.md)
- [State and tool taxonomy](../ai-engineering/application-states/state-and-tool-taxonomy.md)
- [Clarification agent and UX](../requirements/functional/clarification-agent-and-ux.md)
- [Local workflow inspector](../ai-engineering/observability-and-evaluation/workflow-inspector.md)
