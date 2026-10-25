# Issue 4.P — local workflow inspector (Wave 4 step 0)

**Status: Not started**

## User story

As the product owner developing the agentic pipeline, I want to see the
assembled workflow and a selected run in a local UI, so I can understand state
order, configuration, handoffs, tool use, and failures while we build each
state.

## Scope and order

This preparatory issue runs before the application-state slices. It adds the
small inspection boundary needed to make new states visible as they are wired.
Introduce a minimal `BaseWorkflow` for explicit step composition and
dependency execution; the same assembled steps provide the inspector's graph.
The [local workflow inspector design](../../../../ai-engineering/observability-and-evaluation/workflow-inspector.md)
is the functional source of truth for the view.

- [Task 4.P.1 — expose assembled workflow and run inspection data](task-4-p.1-inspection-data.md)
- [Task 4.P.2 — show the workflow and selected run locally](task-4-p.2-local-view.md)

The initial UI can use a small sample workflow until the first product states
exist. As each Wave 4 state is connected, its real configuration and run events
become visible through the same inspection contract. The inspector does not
create a second workflow definition or change how the workflow executes.

## Dependencies and acceptance

- Depends on Wave 2 state/toolbox contracts and the existing developer trace
  surface; target runtime changes belong in `src/product/`.
- One local developer page shows the execution order and dependencies, and
  marks agentic versus deterministic steps.
- Selecting an agentic state shows its description, reasoning/planning
  configuration, input/output DTO fields, versioned prompt template, and
  toolbox with tool descriptions and typed contracts. A selected run also
  shows its resolved prompt snapshot and effective toolbox.
- Selecting a run shows the reached states, their actual input/output values,
  tool outcomes, clarification child-state invocation and wait, and failures
  on that same workflow map.
- The data displayed matches the assembled configuration and actual execution;
  the developer UI remains separate from the user-facing chat experience.
