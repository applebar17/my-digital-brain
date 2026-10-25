# Issue 4.P — local workflow inspector (Wave 4 step 0)

**Status: Implemented for review — configuration-only local slice**

## User story

As the product owner developing the agentic pipeline, I want to see an
assembled workflow's runtime configuration in a local page, so I can review
state order, handoffs, prompts, toolboxes, and DTOs while we build each state.

## Scope and order

This preparatory issue runs before the application-state slices. Introduce a
minimal `BaseWorkflow` for explicit step composition and dependency execution;
the same assembled steps provide a standalone Python/HTML inspector view.
The [local workflow inspector design](../../../../ai-engineering/observability-and-evaluation/workflow-inspector.md)
is the functional source of truth for the view.

- [Task 4.P.1 — expose assembled workflow and run inspection data](task-4-p.1-inspection-data.md)
- [Task 4.P.2 — show the workflow and selected run locally](task-4-p.2-local-view.md)

The initial page uses a clearly marked sample workflow until product states
exist. As each Wave 4 state is connected, its real assembled configuration
becomes visible through the same inspection contract. Selected-run overlays
and integration into the application frontend are later concerns.

## Dependencies and acceptance

- Depends on Wave 2 state/toolbox contracts; target changes belong in
  `src/product/`, not the application frontend.
- One loopback-only page shows the execution order and dependencies, and marks
  agentic versus deterministic steps.
- Selecting an agentic state shows its description, reasoning/planning
  configuration, input/output DTO fields, current prompt text, and toolbox
  with tool descriptions and typed contracts. No prompt-version field is
  fabricated before prompt versioning exists.
- The data displayed comes from the assembled workflow, not a separate diagram.
