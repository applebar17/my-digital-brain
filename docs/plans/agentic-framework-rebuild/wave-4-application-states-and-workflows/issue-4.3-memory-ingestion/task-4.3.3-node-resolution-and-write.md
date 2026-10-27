# Task 4.3.3 — resolve and create nodes with coherent references

**Status: Not started**

## User story

As the ingestion workflow, I want node candidates and known graph identities
represented in a shared model-facing reference context, so later steps can
reuse the correct identity or create a distinct one without seeing backend IDs.

## What and why

Register the completed node candidates in the shared `ReferenceContext`, run
deterministic owner-scoped identity lookup, then invoke
`NodeResolutionWriteState` with the candidates and bounded match evidence. The
state may select an explicitly supplied existing reference, create a distinct
object through typed graph tools, or invoke clarification when a material
identity gap remains. Local refs are mapped to backend UUIDs only at the
tool/service boundary.

This state uses one main LLM/tool session with no separate framework
reasoning/planning stage. Define its input/output DTOs, prompt, graph and
clarification toolbox, handler mappings, and workflow handoff together.

## Where

- `product.application.states.ingestion` node-candidate/resolution states.
- `product.application.tools` graph node create/update bindings and the
  per-ingestion reference context.

## Functional communication boundary

Input includes typed candidates, deterministic match evidence, inherited
history, and the active reference context. Output contains one explicit
resolution/write outcome per candidate. Any completed result used downstream
returns a local ref and readable identity/summary, not a backend UUID.

## Dependencies and acceptance

- Depends on the approved state order and relevant prior handoff from Issue
  4.0/4.3.2.
- Pull in only the deterministic graph capability or child-state tool required
  by this state's agreed behavior; do not wait for Wave 3 as a whole.
- Reference rendering uses the accepted verbosity and owner conventions.
- Node DTO fields correspond explicitly to graph properties.
- A tool validation/write error returns an explanatory tool result; it does not
  deterministically terminate the whole model interaction.
