# Census application integration files

**Status: In progress**

## Objective

For each file, trace its imports and runtime call path into the current
agentic package. Identify the external contract or application behavior that
must continue to work, and the internal dependency that should be replaced.

## Direct-import files

A repository search of `src/my_digital_brain/` confirms 15 production files
directly importing `my_digital_brain.agentic`. The table is the initial
file-by-file assessment; the linked subsystem inventories continue the review
of callers and boundary details. Treatment labels follow the shared
[census classification](../issue-0.1-scope-and-boundaries/define-census-scope.md).

| Current file | Current role | Useful signal | Do not port | Treatment |
| --- | --- | --- | --- | --- |
| `src/my_digital_brain/chat/activity.py` | Maps agentic state IDs to chat activity copy. | User-facing progress labels and intent. | Coupling product copy to the old state enum. | Review behavior for migration — remap reviewed activity to target states. |
| `src/my_digital_brain/chat/agentic_renderer.py` | Converts run results into chat responses, clarification packets, and diagnostics. | Observable chat response semantics and API mapping. | Old run-result DTO as the target contract. | Keep/adapt integration boundary — preserve chat-facing contract and adapt mapping. |
| `src/my_digital_brain/chat/factory.py` | Composes providers, history, state runner, and chat runtime. | Application composition boundary and dependencies. | Construction of the old agentic runtime stack. | Keep/adapt integration boundary — replace only the agentic wiring. |
| `src/my_digital_brain/chat/runtime.py` | Owns chat session lifecycle, persistence, invocation, and clarification resume. | Stable session and human-interaction behavior. | Current agentic frame/history types at the application boundary. | Keep/adapt integration boundary — retain chat lifecycle, reconnect to target runtime. |
| `src/my_digital_brain/clarification/context_projection.py` | Projects references and caller context for clarification. | Information a clarification interaction needs from its invoker. | Dependence on the old `RefContext` and enum types. | Review behavior for migration — retain required context meaning with target DTOs. |
| `src/my_digital_brain/clarification/toolbox.py` | Implements clarification lookup/context/question capabilities. | Human-facing question behavior and deterministic lookup capabilities. | Old reference types and agentic-specific tool dispatch. | Review behavior for migration — preserve accepted capabilities, rebind to typed tools. |
| `src/my_digital_brain/ingestion/identity_lookup.py` | Performs deterministic graph identity lookup and updates local references. | Candidate lookup behavior and the graph-to-model reference boundary. | Old `RefContext` implementation as the new framework contract. | Review behavior for migration — assess deterministic lookup independently from agentic refs. |
| `src/my_digital_brain/ingestion/pending.py` | Maps runtime results into persisted ingestion pending interactions. | Pause/resume data required by the application. | Old runtime result DTO as the durable interaction contract. | Review behavior for migration — preserve required continuation behavior with target DTOs. |
| `src/my_digital_brain/ingestion/planning_contexts.py` | Builds planning contexts from source, conversation, and graph candidates. | Functional context supplied to each planning step. | Existing state-specific DTO ownership as target schema. | Review behavior for migration — map needed context to accepted DTOs. |
| `src/my_digital_brain/ingestion/planning_guidelines.py` | Constructs purpose-specific planning guidance. | Behavioral instructions and distinctions among planning purposes. | Duplicate or implicit prompt ownership in Python model classes. | Review behavior for migration — retain only approved guidance in versioned prompts. |
| `src/my_digital_brain/ingestion/prompt_builders.py` | Builds ingestion prompt messages and projects history/context. | Required context facts and history projection behavior. | A second prompt/version or history ownership mechanism. | Review behavior for migration — reconcile useful projection with canonical prompt/history docs. |
| `src/my_digital_brain/ingestion/resolution_agent.py` | Runs identity-resolution and clarification-related model/tool behavior. | Resolution purpose, decisions, and caller-visible outcomes. | Existing agentic runtime/tool implementation. | Rebuild from specification — use census evidence to define the replacement state/tool boundary. |
| `src/my_digital_brain/ingestion/resolution_toolboxes.py` | Declares model-facing resolution tool schemas. | Required resolution capabilities and their semantic inputs. | Current schemas as an independent contract source. | Review behavior for migration — retain needed capability meaning, regenerate from typed DTOs. |
| `src/my_digital_brain/ingestion/runtime_service.py` | Composes ingestion stages and deterministic collaborators. | End-to-end sequence and deterministic service seams. | Current mixin composition as the target workflow design. | Review behavior for migration — preserve reviewed sequence; recompose from accepted workflow docs. |
| `src/my_digital_brain/ingestion/runtime_stages.py` | Implements reasoning, planning, extraction, and handoffs. | Stage order, supplied context, and handoff data. | Current stage/mixin implementation and agentic DTO wiring. | Review behavior for migration — retain functional requirements, rebuild against target states. |

`src/my_digital_brain/logging.py` is not a direct importer: it configures the
`my_digital_brain.agentic` logger namespace. It is listed separately below as
an adjacent operational integration.

## Additional execution-path packages

These files are on the ingestion/chat/clarification execution paths even when
they do not directly import `my_digital_brain.agentic`. They must be inspected
to determine which deterministic capabilities and application contracts remain
outside the rebuild.

| Current file/group | Why it is in scope | Census direction |
| --- | --- | --- |
| `chat/`, `api/routes/chat.py`, `clarification/` | API/channel callers, session/message persistence, chat rendering/activity, clarification questions/answers, and resume behavior. | Detailed file-by-file task below; distinguish stable API/channel/data contracts from agentic result/runtime coupling. |
| `ingestion/` | Source through reasoning/planning/extraction/resolution, clarification, graph writes, pause/resume, vectorization, and UAT paths. | Detailed file-by-file tasks below; separately assess deterministic service behavior and agentic orchestration. |
| `prompts/` | Prompt IDs, versions, registry/templates, ingestion/clarification guidance. | Detailed file-by-file task below; preserve approved behavior and version provenance, remap to new states, retire unused prompts. |
| `src/my_digital_brain/logging.py` | Configures the logger name for the old agentic namespace; it does not import the package. | Retain application logging policy; update/remove the namespace when the new package boundary is established. |
| `ai/session/` | Active provider-neutral tool/session loop used by the current state runner. | Detailed boundary assessment below; decide retain/wrap/replace only after comparison with the user’s AI-client package. |
| `ai/providers/`, `ai/client/`, `ai/models.py`, `ai/tools/` | Provider DTOs, completion transport, tool specs/execution, and SDK setup beneath agentic code. | Assess the integration boundary and direct contracts; don’t expand this into an AI-client rebuild without evidence. |

## Required follow-up within this issue

The direct-import table is an initial census, not the complete pipeline map.
The linked tasks must inspect each relevant file individually, record its
disposition and rationale, and add newly discovered callers. Keep the source
inventory in this plan; do not add migration banners to production files.

## Observed current control-flow outline (evidence only)

This records the current implementation path, not the target architecture. The
target boundaries are defined in the linked AI-engineering specifications and
the accepted application/workflow documentation.

```text
Chat route/channel
  -> ChatRuntime persists/loads conversation and calls AgenticRuntime
  -> AgenticRuntime invokes AgenticStateRunner for a configured state
  -> current provider-neutral `ai/session` executes model/tool turns
  -> tool binding invokes deterministic graph/retrieval/clarification capability
     or starts a nested child frame/state
  -> AgenticRunResult / interruption is translated to chat response or persisted
```

The current ingestion implementation follows a deterministic sequence that
invokes LLM-backed reasoning/planning/extraction and resolution at selected
stages. Treat this sequence as evidence to reconcile with the accepted
workflow documentation, not as target truth:

```text
source -> graph-context pack -> reasoning -> entity plan -> identity lookup
       -> entity extraction/assembly/validation -> identity resolution
       -> memory-log plan/extraction -> relationship plan/extraction
       -> resolution proposals -> write plan -> graph executor -> vectorization
```

Clarification can arise within child/tool execution and is represented through
pending interaction/continuation data before the caller resumes. The code has
both `pending_from_session(...)` and `pending_from_agentic(...)`; census the
callers and data paths to determine whether these are intentionally distinct or
duplicated continuation adapters. The new framework should have one clear
owner per continuation contract.

The documented `BaseAgenticState` and `AgenticHistorySession` abstractions are
not implemented under those names in this source tree: current entry points
include `AgenticStateRunner` and `AgenticHistoryService`. Record this as an
implementation gap against the target docs. Do not revise the target contract
to fit the old implementation.

## Per-file record format

Use the shared four-field assessment for every source file: current role,
useful signal, do not port, and one treatment classification with a concise
rationale or open question. Add caller/import details only as evidence needed
to support those fields; do not create a second assessment template. Do not
label stable routes, API DTOs, or storage responsibilities as disposable
merely because their current implementation calls the agentic runtime.
