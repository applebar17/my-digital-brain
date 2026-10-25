# Task 4.P.2 — show the workflow and selected run locally

**Status: Not started**

## User story

As the product owner testing ingestion, I want to inspect the workflow as a
visual sequence and open each state's details, so I can diagnose behavior
without reading backend logs or reverse-engineering provider payloads.

## What and why

Extend the existing developer AI trace area with a read-only Workflow view.
Render agentic and deterministic steps distinctly, their dependency links,
and a detail panel for step description, input/output DTO fields and
descriptions, reasoning/planning configuration, versioned prompt template,
and toolbox contracts. A local run selector overlays observed progress and
lets the developer inspect actual step inputs/results,
resolved prompt snapshot, effective toolbox, tool outputs, nested clarification
state activity and its user-input wait, and failures. The existing detailed
trace remains available from the selected run.

The initial layout may be a simple graph or connected sequence with selectable
cards. It should remain understandable before adopting a visual editor or a
new graph package.

## Where and communication

- Existing frontend entry point: `frontend/src/views/AITraceDebugView.tsx`
  and its developer route; adapt related API/type modules as needed.
- Consume Task 4.P.1's typed composition and run responses from the local
  developer API. Do not embed a separate workflow map in the frontend.
- Use the project's existing development-only access boundary and trace
  redaction rules for actual payloads.

## Verification

Open the local view and confirm an assembled workflow is readable with no run
selected. Select a run and verify one completed step, a tool result, and a
failure or clarification point appear on the same map with their owning state.
Check that clarification appears as a child agentic state with its own
deterministic UI tool and returns its result to the original parent state.
Changing the selected run changes the overlay, not the underlying configured
workflow definition.
