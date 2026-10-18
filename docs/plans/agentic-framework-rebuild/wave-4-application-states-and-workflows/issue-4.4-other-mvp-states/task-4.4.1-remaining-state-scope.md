# Task 4.4.1 — define remaining state scope and typed handoffs

**Status: Not started**

## User story

As the product owner, I want each remaining state classified as required for
the MVP or deferred with its caller and data contract documented, so the
rebuild includes needed capabilities without recreating unused pipeline parts.

## What and why

Review the candidate states in the state taxonomy and Wave 0 evidence. For each
retained state, specify its caller, input purpose/context, deterministic
preparation, tools, structured/final output, and the functional meaning of the
handoff. Create implementation tasks only for accepted MVP scope.

## Where

- `product.application.states` and owning state specification documents.
- This plan's issue/task index for status and dependencies.

## Functional communication DTOs

At a high level, each retained state must state: who invokes it, what functional
context it receives, which child/tool results it consumes, and what result is
returned to its caller. DTO shapes remain state-specific and are defined after
that review.

## Dependencies and acceptance

- Depends on completion/review of the core chat and ingestion state contracts.
- Each candidate is explicitly marked MVP or deferred with a short reason.
- Every MVP state has a functional input/output and caller/handoff described.
- No class or implementation task is created for deferred behavior.
