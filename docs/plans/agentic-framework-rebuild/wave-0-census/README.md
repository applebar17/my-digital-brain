# Wave 0 — current-pipeline census

**Status: Complete**

## Goal

Build an evidence-based, file-by-file inventory of the existing agentic
pipeline before designing replacement waves. The likely outcome is that most
of the current implementation is retired, but no source file is marked for
deletion solely because of its current location or age.

## Issues

- [Issue 0.1 — census scope and boundaries](issue-0.1-scope-and-boundaries/README.md)
- [Issue 0.2 — current agentic package](issue-0.2-agentic-package-census/README.md)
- [Issue 0.3 — application integrations](issue-0.3-integration-census/README.md)
- [Issue 0.4 — contracts, behavior, and test evidence](issue-0.4-contract-and-test-evidence/README.md)

## Completion criteria

- Every file in `src/my_digital_brain/agentic/` has an explicit assessment.
- Every direct application import/caller of that package is inventoried,
  including chat, ingestion, clarification, and other discovered consumers.
- Tests and current runtime behavior are linked to the behaviors they verify.
- Each file assessment separates: useful behavior/contract evidence, details
  not to carry forward, and one treatment classification, with rationale.
- No implementation wave is proposed until the census is complete and any
  material uncertainty is surfaced for review.

Wave 0's census is complete. The file treatments are evidence-based proposals,
not implementation authorization. Review the census dispositions and agree the
replacement scope and waves together before defining implementation tasks; see
the [rebuild plan](../README.md).

## Rules

- This wave is analysis/documentation only; do not change runtime behavior.
- Do not infer that a DTO or behavior should survive unchanged merely because
  the current code defines it.
- Distinguish stable application/API contracts from internal agentic DTOs.
- Link to canonical design documents rather than duplicating their rules.
- Use the file-assessment template in [Plans](../../README.md).
- Update task and issue `Status` values as work is discussed and completed.
