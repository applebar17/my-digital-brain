# Census ingestion orchestration files

**Status: Complete**

## Current call-path finding

The repository contains two distinct ingestion paths; they must not be
conflated:

1. Chat-driven ingestion calls
   `AgenticRuntime._run_memory_ingestion_planning`, which delegates to
   `agentic.runtime_memory.MemoryIngestionRuntimeService` for run and resume.
   This is the active in-repository chat path observed in code.
2. `ingestion.runtime_service.IngestionService` implements a separate
   reasoning/planning/extraction/write pipeline. A repository search found no
   production call site for this service; it is constructed by ingestion tests
   and UAT scripts and exported from the package. The user confirmed this is
   residue from a deprecated migration and should be retired, with no external
   compatibility adapter. Its tests/UAT remain behavioral evidence only, not
   supported application consumers.

The target workflow is defined by the accepted AI/application design docs, not
by either current implementation. The distinction above records where current
behavior is observed so the census can map it accurately.

## Orchestration and handoff files

| Current file | Current role | Useful signal | Do not port | Treatment |
| --- | --- | --- | --- | --- |
| `src/my_digital_brain/ingestion/__init__.py` | Exports ingestion services, domain DTOs, and helpers, including the deprecated `IngestionService`. | DTO and helper imports with independently verified production consumers. | Treat the `IngestionService` export as a supported external contract. | Keep/adapt integration boundary — retain verified DTO/capability exports and remove the `IngestionService` export with the retired pipeline. |
| `src/my_digital_brain/ingestion/service.py` | Re-exports `IngestionService` from `runtime_service.py`. | Historical package import and test/UAT setup evidence. | Compatibility wrapper for a retired service. | Retire — remove the export with the deprecated pipeline; no external compatibility surface is required. |
| `src/my_digital_brain/ingestion/runtime_service.py` | Composes the separate ingestion pipeline and its deterministic/model collaborators. | Historical sequence and behaviors that may be useful when defining the replacement workflow. | Treat it as the active chat ingestion entrypoint or port its mixin structure. | Retire — deprecated parallel pipeline with no production caller. |
| `src/my_digital_brain/ingestion/runtime_pipeline.py` | Runs source processing and continuation stages for `IngestionService`. | Historical stage order and resume scenarios. | Pipeline control through mixin inheritance. | Retire — exclusive orchestration code for the deprecated service. |
| `src/my_digital_brain/ingestion/runtime_stages.py` | Implements reasoning, planning, extraction, and handoffs in that pipeline. | Historical inputs, outputs, and stage-specific context for comparison with target specs. | Implicit handoffs and direct old-agentic DTO wiring. | Retire — exclusive stage implementation for the deprecated service. |
| `src/my_digital_brain/ingestion/runtime_candidate_flow.py` | Prepares and resolves candidate graph content. | Historical candidate lifecycle and identity-resolution scenarios. | Hidden state mutation through service mixins. | Retire — exclusive orchestration mixin; reassess any domain behavior separately from this service. |
| `src/my_digital_brain/ingestion/runtime_completion.py` | Completes graph writes, vectorization, and final ingestion status. | Historical write/vectorization ordering and result scenarios. | Conflating model completion with durable-write completion. | Retire — exclusive orchestration mixin; keep independently consumed write/vector services under their own contracts. |
| `src/my_digital_brain/ingestion/runtime_helpers.py` | Helpers used by the deprecated ingestion pipeline mixins. | Any behavior later confirmed necessary by the target workflow. | Preserve helper module or transformations solely to support the retired pipeline. | Retire — current callers are confined to the deprecated service/mixins. |
| `src/my_digital_brain/ingestion/runtime_uat.py` | Provides UAT-oriented execution paths on the ingestion service. | Test scenarios useful for future end-to-end verification. | Test-only workflow methods embedded in production runtime composition. | Retire with the service; recreate only required scenarios against the target workflow. |
| `src/my_digital_brain/ingestion/pending.py` | Converts session/agent outcomes into ingestion pending interactions. | Human pause/resume information required by callers. | Binding the durable contract to either old result class. | Review behavior for migration — retain required continuation meaning using canonical state/history DTOs. |
| `src/my_digital_brain/ingestion/planning_contexts.py` | Builds typed context for ingestion planning calls. | Relevant source, prior reasoning, and graph-candidate facts. | Treating current packet classes as target DTOs. | Review behavior for migration — crosswalk needed fields to canonical context contracts. |
| `src/my_digital_brain/ingestion/planning_guidelines.py` | Builds purpose-specific planning instructions. | Functional distinctions among entity, memory, relationship, and missing-entity planning. | Duplicated prompt policy in Python constants and versioned templates. | Review behavior for migration — retain approved behavior in the canonical prompt source. |
| `src/my_digital_brain/ingestion/prompt_builders.py` | Projects history and context into model-facing ingestion messages. | Dynamic facts that each step needs to see. | Parallel prompt-version or history ownership. | Review behavior for migration — map required context into the prompt/history framework. |
| `src/my_digital_brain/ingestion/resolution_agent.py` | Runs model-backed resolution/proposal behavior and may route clarification. | Resolution purpose, decision outputs, and relevant read capabilities. | Existing agentic runner and toolbox mechanics. | Rebuild from specification — define the replacement state and typed tool boundary from accepted docs. |
| `src/my_digital_brain/ingestion/resolution_toolboxes.py` | Declares model-facing resolution tool schemas. | Resolution capabilities and intended semantic inputs. | Loose schemas as a second source of DTO truth. | Review behavior for migration — carry required capabilities into explicit typed tool definitions. |
| `src/my_digital_brain/ingestion/resolution_context.py` | Builds context packets about planned/candidate entities for resolution. | Evidence the resolution decision needs from other planned items. | Ambiguous model IDs or a second local-reference scheme. | Review behavior for migration — align fields and reference rendering with canonical context docs. |
| `src/my_digital_brain/ingestion/resolution_proposals.py` | Validates and compiles model proposals into resolution decisions. | Safety conditions and proposal-to-action mapping. | Validation rules invisible to the producing model or duplicated at write time. | Review behavior for migration — preserve necessary deterministic safety and expose actionable feedback. |
| `src/my_digital_brain/ingestion/resolution_write_actions.py` | Applies resolution decisions to candidate/write structures. | Effects and ordering of accepted resolution actions. | Generic action dispatch with hidden multi-step mutation. | Review behavior for migration — define explicit typed actions and a single application owner. |
| `src/my_digital_brain/ingestion/refined_relationships.py` | Normalizes relationship endpoints and candidate references. | Endpoint mapping rules needed before graph writes. | A parallel alias/ref registry for the same concept. | Review behavior for migration — compare with canonical reference context and retain only unique mapping behavior. |
| `src/my_digital_brain/ingestion/reference_registry.py` | Coordinates run-scoped entity/action references in this pipeline. | Local-reference lifecycle and ID mapping evidence. | Two competing reference registries alongside agentic `RefContext`. | Review behavior for migration — determine unique responsibilities and one target owner. |
| `src/my_digital_brain/ingestion/identity_lookup.py` | Performs deterministic graph-backed identity candidate lookup. | Search results and candidate evidence used by resolution/clarification. | Letting backend lookup deterministically decide model identity. | Review behavior for migration — preserve lookup as a typed deterministic capability if callers require it. |
| `src/my_digital_brain/ingestion/protocols.py` | Defines service ports for extraction, validation, resolution, writes, and vectorization. | Concrete dependency boundaries around orchestration. | Broad protocols that obscure missing or ambiguous DTO contracts. | Review behavior for migration — keep only needed, explicit typed boundaries. |
| `src/my_digital_brain/ingestion/ontology.py` | Defines ingestion entity and relationship vocabulary. | Existing graph-supported type/relationship names. | A second ontology competing with graph/domain schema. | Review behavior for migration — identify the canonical domain owner and reference it. |
| `src/my_digital_brain/ingestion/normalization.py` | Applies deterministic normalization to ingestion values/references. | Stable domain normalization rules, if independently required. | Model/prompt policy mixed into persistence normalization. | Review behavior for migration — retain deterministic rules only with a clear domain owner. |
| `src/my_digital_brain/ingestion/idempotency.py` | Provides duplicate-execution/write protection for ingestion operations. | Persistence-safety guarantees and their transaction boundary. | Deterministic identity merging presented as an agentic decision. | Review behavior for migration — preserve only storage/idempotency guarantees confirmed by write services. |

## Completion evidence

All 25 files in this orchestration inventory exist under
`src/my_digital_brain/ingestion/`. The in-repository call-site search found
`IngestionService` construction in tests and UAT scripts, but no application
call site. Per the user's decision, its export in `ingestion/__init__.py` does
not imply a compatibility requirement; retire the service and its exclusive
orchestration path. The
active chat route reaches memory ingestion through `AgenticRuntime` and
`MemoryIngestionRuntimeService`, as recorded in the
[integration call-path census](integration-file-census.md).

The linked
[contracts and deterministic-collaborator census](ingestion-contracts-and-services-census.md)
tracks the other 38 files in the package. Issue 0.4 will map specific tests to
the behaviors they assert; this census does not treat a test as proof that the
tested implementation should survive unchanged.
