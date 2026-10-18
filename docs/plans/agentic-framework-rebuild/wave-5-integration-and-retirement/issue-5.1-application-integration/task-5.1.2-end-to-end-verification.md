# Task 5.1.2 — verify end-to-end chat and ingestion behavior

**Status: Not started**

## User story

As a human tester, I want to submit a representative request, observe a
clarification if needed, and see a coherent final response and stored graph
outcome, so I can validate the rebuilt flow through the actual frontend.

## What and why

Run reproducible E2E scenarios through API, root state, mapped tools, child
states, deterministic services, and frontend rendering. Diagnostics should
identify the failing state/tool and functional context without dumping noisy
provider internals as user-facing content.

## Where

- Existing test/e2e scripts and frontend/API integration tests migrated under
  `product` test/config boundaries.
- Relevant chat and ingestion trace surfaces.

## Functional communication DTOs

Tests assert the API request, state/child invocation inputs, matched tool
results, interaction packet/answer when present, assistant final response, and
persisted domain effects. Correlation IDs may be asserted internally but do
not appear as user-facing answer content.

## Dependencies and acceptance

- Depends on Task 5.1.1 and all required state workflows.
- At minimum cover successful ingestion, clarification-and-resume, mapped tool
  failure followed by agent recovery/final response, and memory query.
- Assert both functional rendered output and expected persistence effects.
- Tests can be run with the documented local/container startup options.
