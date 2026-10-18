# Issue 5.2 — cut over the source namespace and retire old runtime

**Status: Not started**

After the new runtime is integrated and verified, consolidate the supported
application code under `src/product/`, update all callers/configuration/tests,
and remove obsolete `my_digital_brain` agentic implementation. No permanent
compatibility package or duplicate runtime remains.

## Tasks

- [Task 5.2.1 — migrate supported source modules and imports](task-5.2.1-migrate-supported-source.md)
- [Task 5.2.2 — remove superseded package and verify clean cutover](task-5.2.2-retire-old-source-tree.md)

## Dependencies

- [Wave 0 dispositions](../../wave-0-census/issue-0.2-agentic-package-census/agentic-package-file-census.md)
- [Wave 0 integration census](../../wave-0-census/issue-0.3-integration-census/README.md)
- Issue 5.1 E2E verification.

## Functional communication DTOs

No new runtime DTO. This issue migrates the ownership/import boundary while
preserving the already accepted API, state, tool, history, and persistence
contracts.
