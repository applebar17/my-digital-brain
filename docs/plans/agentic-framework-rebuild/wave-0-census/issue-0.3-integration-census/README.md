# Issue 0.3 — application integration census

**Status: In progress**

The inventories are initial screens. During review, each source-file entry
must satisfy the shared assessment fields in
[census scope](../issue-0.1-scope-and-boundaries/define-census-scope.md),
including a single treatment classification and supporting evidence or an
open question.

Inventory every production consumer of the current agentic package and identify
what crosses the boundary: DTOs, state invocations, tool execution, persisted
history, chat activity, and API results. Separate stable application
responsibility from the agentic mechanism that will be replaced.

## Tasks

- [Census direct production imports](integration-file-census.md)
- [Census chat and clarification files](chat-and-clarification-file-census.md)
- [Census ingestion orchestration files](ingestion-orchestration-file-census.md)
- [Census ingestion contracts and deterministic collaborators](ingestion-contracts-and-services-census.md)
- [Census prompts and the AI-session boundary](prompt-and-ai-session-census.md)

## Dependencies

- [Census scope](../issue-0.1-scope-and-boundaries/README.md)
- [Application state taxonomy](../../../../ai-engineering/application-states/state-and-tool-taxonomy.md)
- [System architecture](../../../../architecture/system-architecture.md)
