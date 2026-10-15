# Census application integration files

**Status: In progress**

## Objective

For each file, trace its imports and runtime call path into the current
agentic package. Identify the external contract or application behavior that
must continue to work, and the internal dependency that should be replaced.

## Direct-import files

The following files were found importing `my_digital_brain.agentic` directly.
Confirm the list with a repository-wide import/call-site search and inspect
each implementation before assigning final dispositions.

| Current file | Integration responsibility / useful signal | Initial treatment (verify against docs and callers) |
| --- | --- | --- |
| `src/my_digital_brain/chat/activity.py` | User-visible activity labels are product behavior; current state-ID mapping is an implementation dependency. | Retain UX intent; decouple from current state enum. |
| `src/my_digital_brain/chat/agentic_renderer.py` | Maps run/interruptions to API chat response, clarification packet, and diagnostics. | Retain API behavior/DTO contract; rebuild mapping against new result DTOs. |
| `src/my_digital_brain/chat/factory.py` | Composition root constructs provider, router, history, state runner, and runtime. | Retain application composition boundary; replace agentic wiring. |
| `src/my_digital_brain/chat/runtime.py` | Chat session lifecycle, messages, persistence, clarification answer/resume, and root invocation. | Keep stable chat/API/persistence responsibilities; replace agentic runtime calls. |
| `src/my_digital_brain/clarification/context_projection.py` | Projects caller doubts/context into clarification-facing entity/reference details. | Retain clarified functional input needs; rebuild projection DTO boundary. |
| `src/my_digital_brain/clarification/toolbox.py` | Candidate lookup/context/question capabilities and human-facing question construction. | Preserve accepted clarification behavior and backend capabilities; rebuild typed toolbox integration. |
| `src/my_digital_brain/ingestion/identity_lookup.py` | Deterministic identity search and local-ref registration against graph services. | Keep deterministic identity behavior only if independently useful; replace agentic RefContext coupling. |
| `src/my_digital_brain/ingestion/pending.py` | Converts session/agent results into resumable ingestion pending results. | Preserve pause/resume outcomes; replace current runtime-specific adapters. |
| `src/my_digital_brain/ingestion/planning_contexts.py` | Builds state-specific planning context from source, reasoning, and hydrated graph context. | Preserve functional context requirements; rebuild DTO assembly for new states. |
| `src/my_digital_brain/ingestion/planning_guidelines.py` | Shared planning-specific behavioral guidance. | Re-evaluate prompt ownership; avoid Python constants duplicating prompt templates. |
| `src/my_digital_brain/ingestion/prompt_builders.py` | Formats state context and history into prompts for ingestion calls. | Preserve necessary context facts; rebuild using the versioned prompt/context boundary. |
| `src/my_digital_brain/ingestion/resolution_agent.py` | Calls an LLM-backed resolution proposal flow with read capabilities. | Preserve purpose and output requirements; remove current agentic runtime/tool coupling. |
| `src/my_digital_brain/ingestion/resolution_toolboxes.py` | Declares the resolution agent's model-visible backend tools. | Preserve required capabilities; rebuild as typed tool definitions. |
| `src/my_digital_brain/ingestion/runtime_service.py` | Ingestion entry point and mixin composition, calls reasoning/planning/extraction and deterministic services. | High-value sequence evidence; classify deterministic services separately and rebuild agentic orchestration. |
| `src/my_digital_brain/ingestion/runtime_stages.py` | Reasoning, planning, extraction, and handoff stages. | Functional sequencing/context evidence; do not carry current mixin/state-runner implementation forward by default. |
| `src/my_digital_brain/logging.py` | Configures logger names and levels, including current agentic namespace. | Retain app logging policy; update logger names after package cutover. |

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

For every file, document the production caller, agentic imports, DTOs crossing
the boundary, observable behavior that must remain, what should be replaced,
and the proposed disposition. Include relevant callers that do not import the
package directly if the call graph reveals them. Do not label stable routes,
API DTOs, or storage responsibilities as disposable merely because their
current implementation calls the agentic runtime.
