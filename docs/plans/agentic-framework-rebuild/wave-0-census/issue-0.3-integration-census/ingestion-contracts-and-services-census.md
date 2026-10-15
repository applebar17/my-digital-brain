# Census ingestion contracts and deterministic collaborators

**Status: In progress**

## Principle

Existing DTOs are evidence about required data, not automatically the new
contract. Crosswalk their fields to the domain/API/graph owner and identify
which deterministic services can stay outside the new agentic package.

## Deterministic/context/build/write modules

| File | Useful behavior or data meaning | What to verify / not duplicate | Initial disposition |
| --- | --- | --- | --- |
| `assembly.py` | Candidate data assembled into ingestion graph. | Ownership and deterministic merge semantics. | Candidate deterministic service; verify before retention. |
| `candidate_context.py` | Bounded hydration of candidate context. | Bound/limit policy and reference mapping. | Candidate reusable context service; retype boundary. |
| `context_rendering.py` | Human/model-facing rendering of graph context packs. | Overlap with `RefContext` rendering and prompt context rendering. | Preserve only distinct presentation behavior. |
| `graph_context_pack.py` | Retrieves and compacts graph context for one ingestion source. | Search policy versus agent decision and model-facing projection. | Candidate deterministic retrieval/context builder. |
| `enrichment.py` | Enriches extracted memory logs with planned tasks. | Whether data comes from model output or deterministic enrichment. | Keep functional requirements; separate model and deterministic fields. |
| `validation.py` | Candidate and write-plan validation. | Hard stops versus recoverable model feedback; duplicate graph validation. | Preserve deterministic persistence safety; make model-repair errors actionable. |
| `executor.py` | Applies a validated write plan through graph services. | Transactionality, idempotency, ordering, and failure results. | Strong deterministic capability candidate; decide independently of agentic rebuild. |
| `write_plan.py` | Converts accepted candidate graph to graph mutations. | Mapping completeness and canonical graph DTO alignment. | Inspect deterministic mapping; retain only if contracts remain canonical. |
| `write_plan_helpers.py` | Shared write-plan mapping helpers. | Duplicate or generic conversion logic. | Candidate helper only after call-site review. |
| `write_plan_serializers.py` | Write-plan serialization. | Whether serializers duplicate Pydantic API serialization. | Retain only required persistence/wire format. |
| `exceptions.py` | Ingestion-specific error categories. | Duplicate generic runtime/tool errors. | Preserve stable application error meaning; separate model-recoverable validation. |
| `enums.py` | Ingestion/write-plan statuses. | Leaking internal stages as public API statuses. | Reassign values to canonical contract owner. |
| `extractors/__init__.py` | Extractor public interface. | Old extractor assembly coupling. | Rebuild exports. |
| `extractors/base.py` | Structured focused-LLM extraction execution. | Second tool/session loop or provider plumbing. | Determine if extraction becomes state or typed operation; do not port loop. |
| `extractors/entity.py` | Entity extraction fields and instructions. | Duplicate entity schema outside graph DTO owner. | Extract field semantics; regenerate explicit output DTO. |
| `extractors/relationship.py` | Relationship extraction. | Relationship enum drift versus graph ontology. | Extract functional relation semantics; align to canonical ontology. |
| `extractors/relationship_context.py` | Relationship context extraction. | Difference from relationship/relationship-state contract. | Clarify distinct output need; merge or retire if duplicate. |
| `extractors/claim.py` | Claim extraction fields. | Graph DTO field alignment. | Extract needed behavior/fields. |
| `extractors/perception.py` | Perception extraction fields. | Difference from claims/context records. | Confirm product/domain distinction; preserve only if needed. |
| `extractors/profile.py` | Profile memory extraction. | Profile memory storage and privacy contract ownership. | Cross-reference network/privacy requirements; retype if retained. |
| `extractors/metadata_patch.py` | Node metadata patch extraction. | Duplicate node-patch generation and graph mutation schemas. | Compare with graph patch DTOs; one source of truth. |

## Contract files

| File | Data/behavior to extract | What not to assume | Initial disposition |
| --- | --- | --- | --- |
| `contracts/__init__.py` | Current DTO export map. | Export map equals target ownership. | Rebuild exports after field crosswalk. |
| `contracts/base.py` | Pydantic validation/config conventions. | Separate `IngestionModel` remains necessary. | Compare to canonical DTO base; consolidate. |
| `contracts/source.py` | Source text/provenance and run identifiers. | Internal IDs are model-facing or all source fields belong in prompts. | Preserve required source/API boundary fields; project context separately. |
| `contracts/shared.py` | Temporal/affective common fields. | Shared model implies shared owner or required on every object. | Crosswalk with network/domain DTOs; avoid generic reuse without need. |
| `contracts/context.py` | Graph context item/pack/view shapes. | Current packet shape is an API or prompt contract. | Extract required context fields and render goals. |
| `contracts/planning.py` | Extraction task/plan DTOs. | Planning artifact necessarily executes directly. | Retain task meaning; new state output DTO should match accepted workflow. |
| `contracts/refined_drafts.py` | Reasoning and phased entity/memory/relationship plans. | Current ref/action execution semantics are target. | High-value workflow evidence; redesign each handoff with explicit typed contracts. |
| `contracts/drafts.py` | Structured drafts for entities, relations, claims, perceptions, patches. | Draft and persisted DTO are interchangeable. | Keep separation if functionally needed; make mapping explicit. |
| `contracts/candidates.py` | Candidate graph aggregates and entity/relationship records. | Candidate records belong to LLM runtime. | Determine application ownership and required lifecycle; candidate boundary likely remains useful. |
| `contracts/memory_logs.py` | Memory-log data, source, links, updates, media refs. | Any field can be generated without corresponding graph/API storage. | Map each field to graph persistence and frontend display contract. |
| `contracts/identity_resolution.py` | Candidate lookup, local identity refs, proposal/status types. | Second ref/status model can coexist with agentic `RefContext`. | Compare field-by-field; select one owner for local refs. |
| `contracts/resolution.py` | Resolved-entity map and status. | Resolution proposal, resolution decision, and map have identical roles. | Preserve distinctions only where stage contracts require them. |
| `contracts/resolution_actions.py` | Ordered resolution steps and available action names. | Action planning and execution are same contract. | Extract exact sequence/tool requirements; rebuild DTO-first. |
| `contracts/results.py` | Ingestion outcome and context package. | Internal execution details belong in outward API result. | Preserve user/API-visible status; replace runtime internals. |
| `contracts/pending.py` | Pending clarification and resume information. | Old continuation IDs/snapshots are target API. | Preserve user-continuation needs; derive storage contract separately. |
| `contracts/validation.py` | Validation issues and result shape. | Errors should deterministically stop model work. | Preserve diagnostics; define recoverable model feedback per accepted policy. |
| `contracts/write_plan.py` | Node, relationship, and graph write plan DTOs. | Planning proposal equals accepted/durable mutation. | Preserve explicit mapping if still used; tie fields to graph write DTOs. |
| `contracts/vector_scopes.py` | Vector retrieval scopes, strategy, hit and request data. | Agentic rebuild owns vector retrieval schema. | Likely deterministic retrieval boundary; assess independent owner. |

## Completion output

Inspect validators, graph writes, service callers, and tests before confirming
any “retain” candidate. In particular, explain the ownership and field mapping
between ingestion drafts/candidates, graph write models, and stored graph
objects. Record field-level uncertainty for the later contract-definition
work; do not expand Wave 0 into redesigning those DTOs.
