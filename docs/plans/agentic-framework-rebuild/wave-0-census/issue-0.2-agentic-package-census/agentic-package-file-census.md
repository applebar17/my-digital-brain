# Census the agentic package files

**Status: In progress**

## Objective

Read each listed source file and document what it does today, what behavior or
contract information is useful to the rebuild, what should not be carried
forward, and its proposed disposition. File names and apparent abstractions
are not evidence of target value; inspect implementations and relevant tests.

The inventory below is an initial screen, not a final disposition. Complete
each assessment using the shared fields in [census scope](../issue-0.1-scope-and-boundaries/define-census-scope.md):
current role, useful signal, do not port, and one treatment classification
with evidence or an open question. The table combines role and useful signal
for readability; unresolved treatment wording is reviewed task by task.

## File-by-file initial assessment

These are census findings from source inspection, not a decision to preserve
the present code. “Rebuild behavior” means extract the useful responsibility
or contract evidence and implement it anew; it does not mean copy the file.

| Source file | Current role / useful signal | What not to carry forward | Treatment (with evidence/open point) |
| --- | --- | --- | --- |
| [`__init__.py`](../../../../../src/my_digital_brain/agentic/__init__.py) | Reveals the public runtime/DTO surface and how widely concepts are coupled. | Broad convenience exports that obscure ownership and encourage cross-layer imports. | Reference only; replace exports at new boundaries. |
| [`base.py`](../../../../../src/my_digital_brain/agentic/base.py) | `extra="forbid"`, enum serialization, and timezone-aware timestamps are useful contract conventions to evaluate against AI DTO owners. | Agentic-specific shared model base if it duplicates canonical AI/application model policy. | Rebuild behavior only if needed; verify canonical DTO base first. |
| [`contexts.py`](../../../../../src/my_digital_brain/agentic/contexts.py) | Captures current functional inputs/outputs for chat, reasoning, planning, query, ingestion, graph mutation, contradiction, profile, and maintenance. | The 1,200-line cross-domain DTO collection, broad `Any` payloads, coupled validators, and implementation-shaped packets. | Reference-only field/behavior inventory; define new DTOs at owning boundaries. |
| [`enums.py`](../../../../../src/my_digital_brain/agentic/enums.py) | Values reveal current state names, transcript/tool statuses, reference kinds, ingestion phases, and domain concepts. | One mixed enum module coupling runtime, domain, graph, and presentation concepts. | Reference values; redistribute/redefine enums with each rebuilt contract. |
| [`history.py`](../../../../../src/my_digital_brain/agentic/history.py) | Documents intended shared-vs-local history projections, clarification promotion, source inclusion, compaction, and prompt-safe filtering. | The 800-line service that knows chat storage records, ingestion payloads, agentic DTOs, and prompt serialization at once. | Rebuild the agreed history behavior under the documented history-session design; do not port service structure. |
| [`messages.py`](../../../../../src/my_digital_brain/agentic/messages.py) | Makes transcript roles and tool-call/tool-output message shape explicit. | Locally generated tool-call IDs and a second neutral transcript model if AI-session DTOs already own provider transcript semantics. | Contract comparison required; likely retire or replace from one transcript owner. |
| [`mutations.py`](../../../../../src/my_digital_brain/agentic/mutations.py) | Maps graph node labels to explicit create/patch DTOs and makes model-facing fields inspectable. | Reusing this registry as agentic orchestration policy; identity-gap behavior embedded beside schema mapping needs product review. | Preserve graph DTO ownership; rebuild model tool declarations from approved graph contracts. |
| [`planning.py`](../../../../../src/my_digital_brain/agentic/planning.py) | Shows that planning and extraction are separately invocable model operations with structured results. | Thin service wrappers tied to current runner/configuration and context model classes. | Functional reference; re-express through the new state/session API. |
| [`planning_contracts.py`](../../../../../src/my_digital_brain/agentic/planning_contracts.py) | Records planning purpose/action/result fields and how prior reasoning/context is rendered to later calls. | One broad planning DTO family plus ad-hoc prompt serialization helpers. | Extract accepted action semantics; define clear per-step DTOs in target ownership. |
| [`query.py`](../../../../../src/my_digital_brain/agentic/query.py) | Shows deterministic retrieval/context preparation before a grounded answer-generation call. | State-specific service tied to existing context and runtime DTOs if this belongs in a new application state. | Rebuild behavior as a memory-query state; retrieval service remains a separate dependency candidate. |
| [`reasoning.py`](../../../../../src/my_digital_brain/agentic/reasoning.py) | Shows reasoning as a configurable structured model call that can be invoked by ingestion. | Service wrapper coupled to current state runner, prompt registry, and tool execution context. | Rebuild behavior through new state framework; retain only agreed reasoning artifact semantics. |
| [`refs.py`](../../../../../src/my_digital_brain/agentic/refs.py) | Strong functional evidence for local model-facing refs, backend UUID mapping, existing/proposed/created status, endpoint refs, and readable prompt inventory. | Current large registry/packet builder implementation and its validation rules without reviewing user-approved reference semantics. | High-value functional reference; rebuild only the agreed small reference context and renderer. |
| [`runtime.py`](../../../../../src/my_digital_brain/agentic/runtime.py) | Exposes actual root/child/resume lifecycle, tool handoff, clarification continuation, and persistence sequence—including failure history. | Monolithic runtime coordinating provider state, chat history, ingestion, clarification, storage, and trace details. | Reference only; derive behavior requirements and replace the orchestration layer. |
| [`runtime_helpers.py`](../../../../../src/my_digital_brain/agentic/runtime_helpers.py) | Identifies current context/prompt enrichment, trace summaries, and owner/reference projections. | Private helpers coupled to oversized runtime/state DTOs and untyped recursive payload discovery. | Reference selected behavior; no helper migration by default. |
| [`runtime_memory.py`](../../../../../src/my_digital_brain/agentic/runtime_memory.py) | Reveals current phase sequencing, write-plan action execution, context/ref binding, and recovery/result behavior. | Agentic runtime module containing ingestion-specific execution and bespoke ref/action validation. | Cross-reference ingestion census; replace orchestration, evaluate deterministic graph-writing services independently. |
| [`runtime_models.py`](../../../../../src/my_digital_brain/agentic/runtime_models.py) | Shows current state invocation/result, tool event, interruption, and run-result information consumed by chat/ingestion. | Multiple overlapping result wrappers and `Any`-typed execution/context fields. | Compare each field against API, session, and orchestration contracts; redefine only needed DTOs. |
| [`runtime_state.py`](../../../../../src/my_digital_brain/agentic/runtime_state.py) | Documents state-specific prompt selection, schema parsing, tool loop entry, continuation, and activity emission. | State runner that mixes AI session invocation, prompt/context assembly, state config, event collection, continuation, and UI callbacks. | Reference protocol behavior; replace as part of the new framework. |
| [`state.py`](../../../../../src/my_digital_brain/agentic/state.py) | Enumerates current states, purposes, expected context/result types, and state-specific tool exposure. | String-named DTO contracts and one large hard-coded state configuration map as the new extension mechanism. | Functional inventory; re-declare states and toolbox via typed target configs. |
| [`tools/__init__.py`](../../../../../src/my_digital_brain/agentic/tools/__init__.py) | Shows current intended tool-layer public concepts. | Re-export coupling across registry, factory, and binding internals. | Retire with old package; target exports only stable public types. |
| [`tools/bindings.py`](../../../../../src/my_digital_brain/agentic/tools/bindings.py) | Maps model-visible capabilities to graph, retrieval, clarification, and child-state operations; valuable as a capability inventory. | A 1,900-line handler object mixing unrelated tool domains, stateful mutable dispatch context, and serialization/error policy. | Split capability inventory by owning service; rebuild typed handler bindings. |
| [`tools/factory.py`](../../../../../src/my_digital_brain/agentic/tools/factory.py) | Shows toolbox schema and executable mapping need to be composed from the same selected definitions. | `Callable[..., ToolResult]`, `**kwargs` dispatch and mutation of shared execution context for handler identity. | Rebuild behavior as typed tool registration; old implementation retired. |
| [`tools/registry.py`](../../../../../src/my_digital_brain/agentic/tools/registry.py) | Valuable inventory of model-visible tool names, descriptions, schemas, state access, and graph DTO links. | 687-line mixed registry with manually duplicated schema/DTO translation and unrelated tool families. | Re-author from approved input/output DTOs in target toolbox modules. |
| [`tools/specs.py`](../../../../../src/my_digital_brain/agentic/tools/specs.py) | Demonstrates provider-facing strict-schema translation and descriptions. | Generic JSON-schema helper API if the target tool DTO layer can generate the provider schema directly. | Compare against `ai/tools` and AI contract owners; avoid duplicate schema construction. |

## Evidence pointers

- [`test_agentic_foundation.py`](../../../../../tests/test_agentic_foundation.py)
  covers current message/context/reference/planning DTO semantics.
- [`test_agentic_runtime.py`](../../../../../tests/test_agentic_runtime.py)
  covers root/child frames, errors, tool correlation, resume, and structured
  state execution.
- [`test_agentic_history.py`](../../../../../tests/test_agentic_history.py)
  covers history projection and promotion behaviors.
- [`test_agentic_tool_bindings.py`](../../../../../tests/test_agentic_tool_bindings.py)
  covers schema exposure, graph writes, clarification handoff, and tool errors.

The assessments are centralized here; production files will not receive
migration banners or census comments.
