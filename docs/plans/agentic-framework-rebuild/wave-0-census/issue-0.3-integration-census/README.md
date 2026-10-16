# Issue 0.3 — application integration census

**Status: Complete**

## Source-of-truth rule

The accepted technical and functional documents define the target. Source code
and tests are evidence of current callers, data crossings, persistence, and
observable behavior; they do not override an accepted target contract. Record
any implementation/documentation mismatch as a discrepancy and identify the
owning document to reconcile. Do not infer a new design or implementation task
from current code alone.

The inventories are initial screens. During review, each source-file entry
must satisfy the shared assessment fields in
[census scope](../issue-0.1-scope-and-boundaries/define-census-scope.md),
including a single treatment classification and supporting evidence or an
open question.

Inventory the production consumers and dependencies around the current agentic
package. Record DTOs, state invocations, tool execution, persisted history,
chat activity, and API results that cross boundaries. Identify stable
application responsibilities against accepted docs, separately from old
agentic mechanisms that the rebuild replaces.

## Tasks

- [Census direct production imports](integration-file-census.md)
- [Census chat and clarification files](chat-and-clarification-file-census.md)
- [Census ingestion orchestration files](ingestion-orchestration-file-census.md)
- [Census ingestion contracts and deterministic collaborators](ingestion-contracts-and-services-census.md)
- [Census prompts and the AI-session boundary](prompt-and-ai-session-census.md)

The census confirms that chat ingestion uses the current `AgenticRuntime`;
the package-exported `ingestion.IngestionService` is deprecated migration
residue with no production caller and is marked for retirement without an
adapter. Verified API/RAG/graph/clarification consumers of adjacent contracts
are assessed separately and are not discarded merely because the old service
used them.

## Dependencies

- [Census scope](../issue-0.1-scope-and-boundaries/README.md)
- [Application state taxonomy](../../../../ai-engineering/application-states/state-and-tool-taxonomy.md)
- [System architecture](../../../../architecture/system-architecture.md)
