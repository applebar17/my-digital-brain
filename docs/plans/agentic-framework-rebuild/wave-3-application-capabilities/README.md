# Wave 3 — application capabilities (demand-driven)

**Status: Not started**

## Role in the workflow-first plan

This wave is no longer a prerequisite inventory or a horizontal migration of
graph, retrieval, and interaction services. Its issues are capability
candidates to be activated only when an agreed state in Wave 4 requires them.
The state task defines the functional operation and DTO boundary first; the
smallest deterministic function and, when needed, model-facing tool are then
implemented as part of that state's vertical slice.

## Issues

- [Issue 3.1 — migrate deterministic services required by the MVP](issue-3.1-deterministic-services/README.md)
- [Issue 3.2 — define product tool DTOs and bindings](issue-3.2-product-tools/README.md)

## Dependencies and boundaries

- Uses the typed generic contracts and toolbox composition established in Wave
  2.
- Existing graph, vector, chat, and clarification service contracts are
  inventoried in [Wave 0](../wave-0-census/README.md).
- A Wave 3 issue is not started merely because it appears here. Link its scope
  to the specific accepted state task that needs it.
- Do not move a service just to match a desired folder; adapt only the minimal
  deterministic capability required by that state.

## Exit evidence

- Every capability pulled into a state slice has explicit typed inputs and
  outputs and a clear deterministic function or child-state mapping.
- No application agentic policy is placed inside graph/vector storage classes.
