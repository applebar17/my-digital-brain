# Census ingestion orchestration files

**Status: In progress**

## Principle

The goal is to separate ingestion's user/domain behavior and deterministic
capabilities from the current agentic implementation. Keep the sequence as
evidence; do not assume either that all ingestion code is agentic or that the
current `IngestionService` structure is the target.

## Orchestration and LLM handoff files

| File | Useful rebuild evidence | Do not carry forward by default | Initial disposition |
| --- | --- | --- | --- |
| `src/my_digital_brain/ingestion/__init__.py` | Current public package surface. | Convenience exports binding old runtime types. | Rebuild exports. |
| `src/my_digital_brain/ingestion/service.py` | Compatibility-facing export of `IngestionService`. | Thin alias if no external caller requires it. | Find callers; retire if internal-only and superseded. |
| `src/my_digital_brain/ingestion/runtime_service.py` | Production ingestion composition, dependencies, and domain entry. | Current mixin layout and direct old-agentic service ownership. | High-value behavior/DI evidence; replace agentic orchestration, preserve needed deterministic collaborators. |
| `src/my_digital_brain/ingestion/runtime_pipeline.py` | Source processing sequence and resume path. | Pipeline control mixed into current service inheritance. | Rebuild sequence from functional requirements and agreed workflow architecture. |
| `src/my_digital_brain/ingestion/runtime_stages.py` | Reasoning, planning, extraction, and state/tool handoffs. | Mixin implementation and implicit context handoff. | High-value state/context inventory; implement with explicit DTOs later. |
| `src/my_digital_brain/ingestion/runtime_candidate_flow.py` | Candidate/memory-log/relationship preparation sequence. | Hidden mutation through mixin-owned state. | Preserve required stage outcomes; redesign handoffs explicitly. |
| `src/my_digital_brain/ingestion/runtime_completion.py` | Graph write completion, vectorization, and outcome status. | Coupling write success to LLM state completion. | Inspect deterministic write/vector services separately; retain API-visible completion semantics. |
| `src/my_digital_brain/ingestion/runtime_helpers.py` | Shared deterministic context/extraction helpers. | General helper pile spanning model calls and domain services. | Split by verified domain/service ownership; no direct migration assumed. |
| `src/my_digital_brain/ingestion/runtime_uat.py` | Current test/UAT entry paths and fixtures. | Test-only methods in production service mixins. | Preserve useful UAT coverage outside production orchestration. |
| `src/my_digital_brain/ingestion/pending.py` | Pending interaction and resume result translation. | Adapter tied to one current session result class. | Preserve pause/resume contract; replace translation type. |
| `src/my_digital_brain/ingestion/planning_contexts.py` | Meaningful context assembly for planning calls. | Runtime-specific prompt packet construction. | Extract field requirements; new typed context DTOs own the contract. |
| `src/my_digital_brain/ingestion/planning_guidelines.py` | Ingestion-specific behavior rules for planning. | Prompt policy duplicated between source constants, templates, and schemas. | Reconcile once with canonical prompt source. |
| `src/my_digital_brain/ingestion/prompt_builders.py` | Context/history inclusion and model-facing prompt formatting. | Prompt rendering hidden inside pipeline service concerns. | Preserve required dynamic context; route through canonical prompt lifecycle. |
| `src/my_digital_brain/ingestion/resolution_agent.py` | LLM-backed resolution purpose and proposal output. | Old runner/tool-call context integration. | Rebuild as typed agentic state/tool according to approved state taxonomy. |
| `src/my_digital_brain/ingestion/resolution_toolboxes.py` | Resolution capability schemas and read/write limits. | Separate loose schemas duplicating DTO definitions. | Preserve allowed capability semantics; regenerate from explicit DTOs. |
| `src/my_digital_brain/ingestion/resolution_context.py` | Candidate/entity evidence supplied for resolution decisions. | Unclear mix of persisted IDs and local refs without typed mapping. | Extract context requirements and ID semantics; define canonical contract. |
| `src/my_digital_brain/ingestion/resolution_proposals.py` | Proposal validation and conversion to resolution actions. | Validation policy not visible to the producing LLM or duplicated at write time. | Identify functional safety rules; redesign as explicit DTO/service validation. |
| `src/my_digital_brain/ingestion/resolution_write_actions.py` | Applies accepted resolution results to candidate/write structures. | Implicit, multi-step mutation hidden behind generic action dispatch. | Preserve required effects; define exact typed actions and owner. |
| `src/my_digital_brain/ingestion/refined_relationships.py` | Relationship reference normalization and endpoint mapping. | Parallel alias/ref registries for the same concept. | Compare with canonical graph/reference context; retain only unique behavior. |
| `src/my_digital_brain/ingestion/reference_registry.py` | Run-scoped entity/action ref coordination. | Duplicate `RefContext` functionality or hidden second identity source. | Compare directly to `agentic/refs.py`; unify or retire, not both. |
| `src/my_digital_brain/ingestion/identity_lookup.py` | Deterministic graph-backed identity candidate lookup. | Ref registry coupling or semantic fallback that changes agent decision. | Keep deterministic lookup as a candidate capability; define a typed service boundary. |
| `src/my_digital_brain/ingestion/protocols.py` | Existing ports for extractors, resolution, write plan, and vectorization. | Broad/ambiguous protocols that mask incomplete DTO contracts. | Inventory useful dependency seams; retype explicit inputs/outputs. |
| `src/my_digital_brain/ingestion/ontology.py` | Allowed graph entity/relationship vocabulary used in ingestion. | Agent prompt duplication if graph/domain owns canonical vocabulary. | Preserve domain vocabulary at canonical owner; reference it from prompts/tools. |
| `src/my_digital_brain/ingestion/normalization.py` | Deterministic text/reference normalization rules. | Model-oriented normalization mixed into persistence or tool protocol. | Keep only deterministic domain normalization that remains required. |
| `src/my_digital_brain/ingestion/idempotency.py` | Duplicate execution/write protection. | Agentic decisions encoded as deterministic duplicate suppression. | Inspect scope carefully; retain only persistence/idempotency guarantees. |

## Completion output

For each row, add concrete callers, input/output DTOs, and tests; distinguish
model-decision stages from deterministic work. Identify duplicate ownership
between the run reference registry and agentic `RefContext`, and note any
missing functional decision without resolving it by assumption.
