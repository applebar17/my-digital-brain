# Census ingestion orchestration files

**Status: In progress**

## Current call-path finding

The repository contains two distinct ingestion paths; they must not be
conflated:

1. Chat-driven ingestion calls
   `AgenticRuntime._run_memory_ingestion_planning`, which delegates to
   `agentic.runtime_memory.MemoryIngestionRuntimeService` for run and resume.
   This is the active in-repository chat path observed in code.
2. `ingestion.runtime_service.IngestionService` implements a separate
   reasoning/planning/extraction/write pipeline. A repository search found no
   non-test production call site for this service; it is constructed by
   ingestion tests and exported from the package. Its sequence is evidence,
   not proof that it is the active chat pipeline.

The target workflow is defined by the accepted AI/application design docs, not
by either current implementation. The distinction above records where current
behavior is observed so the census can map it accurately.

## Orchestration and handoff files

| Current file | Current role | Useful signal | Do not port | Treatment |
| --- | --- | --- | --- | --- |
| `src/my_digital_brain/ingestion/__init__.py` | Exports ingestion services, domain DTOs, and helpers. | Existing import surface and DTO/service consumers. | Assume every export is a required public contract. | Review behavior for migration — retain only exports with verified production or accepted use. |
| `src/my_digital_brain/ingestion/service.py` | Re-exports `IngestionService` from `runtime_service.py`. | Existing package-level constructor import used by tests and UAT scripts. | Keep a compatibility wrapper without a confirmed application consumer need. | Decision needed — no in-repo application caller was found; confirm whether external consumers depend on this import before retirement. |
| `src/my_digital_brain/ingestion/runtime_service.py` | Composes the separate ingestion pipeline and its deterministic/model collaborators. | Sequence, dependency seams, and result behavior exercised by tests and UAT scripts. | Treat it as the active chat ingestion entrypoint or port its mixin structure. | Review behavior for migration — use as evidence; no in-repo application call site found. |
| `src/my_digital_brain/ingestion/runtime_pipeline.py` | Runs source processing and continuation stages for `IngestionService`. | Stage order and resume behavior in this tested path. | Pipeline control through mixin inheritance. | Review behavior for migration — compare required sequence with accepted workflow docs. |
| `src/my_digital_brain/ingestion/runtime_stages.py` | Implements reasoning, planning, extraction, and handoffs in that pipeline. | Inputs, outputs, and stage-specific context. | Implicit handoffs and direct old-agentic DTO wiring. | Review behavior for migration — preserve only stage behavior confirmed by the target workflow. |
| `src/my_digital_brain/ingestion/runtime_candidate_flow.py` | Prepares and resolves candidate graph content. | Candidate lifecycle and sequencing around identity resolution. | Hidden state mutation through service mixins. | Review behavior for migration — reconcile behavior with canonical ingestion flow. |
| `src/my_digital_brain/ingestion/runtime_completion.py` | Completes graph writes, vectorization, and final ingestion status. | Write/vectorization ordering and observable result semantics. | Conflating model completion with durable-write completion. | Review behavior for migration — assess deterministic collaborators independently. |
| `src/my_digital_brain/ingestion/runtime_helpers.py` | Shared helpers used by ingestion pipeline stages. | Concrete transformations or batching rules with real callers. | A general helper module mixing unrelated model and domain behavior. | Review behavior for migration — retain only helpers with a clear single owner and consumer. |
| `src/my_digital_brain/ingestion/runtime_uat.py` | Provides UAT-oriented execution paths on the ingestion service. | Existing end-to-end/UAT coverage and scenarios. | Test-only workflow methods embedded in production runtime composition. | Review behavior for migration — keep useful test scenarios outside the target runtime. |
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
call site; its export in `ingestion/__init__.py` is not itself evidence of an
application caller. The
active chat route reaches memory ingestion through `AgenticRuntime` and
`MemoryIngestionRuntimeService`, as recorded in the
[integration call-path census](integration-file-census.md).

The linked
[contracts and deterministic-collaborator census](ingestion-contracts-and-services-census.md)
tracks the other 38 files in the package. Issue 0.4 will map specific tests to
the behaviors they assert; this census does not treat a test as proof that the
tested implementation should survive unchanged.
