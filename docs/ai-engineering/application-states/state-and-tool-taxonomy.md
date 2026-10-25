# State and tool taxonomy with current map

## Purpose and status

**Binding application-integration specification.** This document classifies
current functionality into deterministic services/tools, LLM-only agentic
states, and dynamic agentic states. It maps the existing runtime toward the
documented `BaseAgenticState` framework without authorizing implementation or
retaining parallel runtime paths.

## Core taxonomy

| Concept | Responsibility | LLM involvement |
| --- | --- | --- |
| Deterministic service/function | Typed backend capability with defined input and output. | None. |
| Tool protocol | Typed adapter exposing a capability to a model: schema, handler, output, and provider-call correlation. | Surrounds the capability. |
| Deterministic tool | Tool handler directly invokes a backend service. | None after the model chooses the tool. |
| LLM-only agentic state | `BaseAgenticState` with no toolbox. | One structured/final LLM session by default. |
| Dynamic agentic state | `BaseAgenticState` with an explicit toolbox. | The LLM may use normal tool rounds. |
| Agentic tool | Typed tool handler that starts a child agentic state and returns one compact parent tool output. | Child state owns its local LLM session. |
| Workflow-backed tool | Typed tool handler bound to a concrete `BaseWorkflow` subclass method; its compact workflow result becomes one matched caller tool output. | The workflow invokes its configured agentic states. |
| Composite agentic state/tool | Deterministic preparation followed by an agentic state. | Only the agentic portion uses an LLM. |
| Orchestrator | Initializes session/history, invokes root states, and persists accepted outcomes. | None unless intentionally implemented as a state. |

The client/runtime owns the provider transcript and tool-call protocol. The
application decides only which typed capability to expose and which state to
invoke. See [tool-calling protocol](../runtime/tool-calling-protocol.md),
[agentic state framework](../runtime/agentic-state-framework.md), and
[agentic history session](../runtime/agentic-history-session.md).

A parent agentic state can expose either a child agentic state or a workflow as
a tool. Both use the same registered-tool boundary: validated input reaches the
bound handler, one typed result returns as the matched parent tool output, and
the parent state resumes. The distinction affects only the bound executable:
an agentic tool invokes one child state, while a workflow-backed tool invokes a
workflow that may coordinate several states and deterministic steps.

## Tool protocol around backend classes

The LLM never calls graph, vector, or other backend service classes directly.
A typed tool adapter stands in front of the capability:

```text
model tool call
  -> ToolDefinitionDTO: name, description, input DTO
  -> validated handler with bound service dependencies
  -> deterministic service call, child AgenticState invocation, or workflow method
  -> typed OutputDTO or error -> client ToolOutputDTO matched to provider call ID
  -> provider/model continues
```

For example, a graph creation tool validates `CreateMemoryLogInputDTO`, invokes
the deterministic graph service, and returns `CreateMemoryLogOutputDTO`. A
vector-search tool validates a search request, invokes hybrid/semantic search,
and returns a typed context packet. The chatbot's `ingest_memory` tool invokes
the bound `MemoryIngestionWorkflow.ingest_memory` method and returns its typed
workflow result. The model chooses whether to call each tool; the bound handler
owns its execution.

## `MemoryQueryState` example

`MemoryQueryState(BaseAgenticState)` is a composite agentic state:

```text
MemoryQueryState.invoke(...)
  -> deterministic hybrid/vector retrieval
  -> build MemoryQueryContextPacket
  -> main LLM session receives selected history, request, and packet
  -> optional read-only toolbox enlarges the packet when needed
  -> MemoryQueryResultPacket
```

When an LLM parent may decide whether to query memory, a `query_memory` agentic
tool starts this state and converts its result into the parent’s one matched tool
output. When application code always needs memory context, it invokes
`MemoryQueryState` directly before its own state/session work.

The current `query_memory` binding already follows this composite shape: it
performs deterministic semantic retrieval, builds query context, then starts
the `MEMORY_QUERY` child frame. Its future class owns that sequence explicitly.

## Current-to-target map

| Current capability | Current broad shape | Target framework classification |
| --- | --- | --- |
| Chat runtime/session startup | Chat and agentic-runtime orchestration | Deterministic orchestrator; creates `AgenticHistorySession` and invokes root state. |
| `conversation_entry` | LLM router with top-level tools | Dynamic `ConversationEntryState`. |
| Graph read/write operations | Backend handlers exposed to current states | Deterministic typed tools over graph services. |
| Hybrid/vector retrieval | Backend service and context prework | Deterministic retrieval service/tool. |
| `query_memory` | Retrieval prework plus `MEMORY_QUERY` child frame | Composite dynamic `MemoryQueryState`; retrieval first, read-only toolbox available for enlargement. |
| `ingest_memory` | Child agentic frame in the current code | Workflow-backed tool bound to `MemoryIngestionWorkflow(BaseWorkflow).ingest_memory`; configured ingestion states own any reasoning/planning calls. |
| `memory_creation` | Tool-heavy child state | Dynamic `MemoryCreationState`. |
| `graph_update` | Tool-heavy child state | Dynamic `GraphUpdateState`. |
| `clarification_agent` | Tool-using child state that can pause | Dynamic `ClarificationAgentState`, continuation-capable. |
| `contradiction_review` | Structured LLM state with read/clarification tools | Dynamic `ContradictionReviewState`. |
| `memory_log_extraction` | Structured LLM state with read/clarification tools | Dynamic `MemoryLogExtractionState` under current behavior. |
| `reasoning_checkpoint` | Generic structured LLM state | Optional reasoning-stage capability of a concrete state. |
| `planning_checkpoint` | Generic structured LLM state | Optional planning-stage capability of a concrete state. |
| Node/log/edge planning prompts | Focused structured planning calls | State-specific planning-stage configurations. |
| `profile_duplication` | LLM-only structured state | LLM-only `ProfileDuplicationState` if retained as an MVP capability. |

Prompt-level planners, extractors, and reasoning transforms are not automatically
state classes. They become configuration/internal steps when only their owning
state needs them. They receive a standalone `BaseAgenticState` subclass only
when another caller must independently invoke and consume their result.

## Required specification for each concrete state

Each state integration document must state, briefly:

1. **Invocation**: direct backend call, parent agentic tool, top-level chat
   tool, or supported combination.
2. **DTO contracts**: invocation/context input and final output; reuse current
   contracts where they remain suitable.
3. **Deterministic preparation**: required service calls and the functional
   context packet they build.
4. **History and context engineering**: selected `AgenticHistorySession` view,
   system-prompt inputs, deterministic context, and optional reasoning/planning
   artifacts.
5. **Agent behavior**: purpose, toolbox availability, and whether the state is
   LLM-only or dynamic.
6. **Structured result**: expected final artifact and its functional use.
7. **Completion behavior**: final result, parent tool output, or continuation
   when awaiting user input.

Prompt templates and toolbox registration/configuration are specified in their
dedicated documents. Concrete state records select those configurations; they
must not create alternative state or tool classifications.
