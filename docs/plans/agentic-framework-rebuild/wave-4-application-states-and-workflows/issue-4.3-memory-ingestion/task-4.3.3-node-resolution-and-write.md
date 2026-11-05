# Task 4.3.3 — resolve and create nodes with coherent references

**Status: Completed — workflow continuation explicitly deferred to Task 4.3.6**

## User story

As the ingestion workflow, I want node candidates and known graph identities
represented in a shared model-facing reference context, so later steps can
reuse the correct identity or create a distinct one without seeing backend IDs.

## What and why

Register the completed node candidates in the shared `ReferenceContext`, apply
launch-configurable deterministic batching, and prepare owner-scoped identity
lookup for each batch. `NodeResolutionWriteState` receives one prepared batch
with bounded current match evidence.
The state may select an explicitly supplied existing reference, create a
distinct object, update an existing object through its explicit subtype patch,
or invoke clarification when a material identity gap remains. Local refs are
mapped to backend UUIDs only at the tool/service boundary.

Batch defaults are a maximum size of 15 and a dedicated-type minimum of 5.
Complete and substantial same-type groups use dedicated batches; smaller
remainders are pooled into mixed batches. Both values are configured at
application launch. The state implementation remains the same for every
batch, while its graph-action schema is narrowed to the node types present in
that invocation.

This state uses one main LLM/tool session with no separate framework
reasoning/planning stage. This task defines its input/output DTOs, prompt,
graph and clarification toolbox, handler mappings, deterministic batching, and
per-batch lookup preparation.

## Explicit deferral to Task 4.3.6

Task 4.3.3 does not add a partial workflow continuation implementation. Task
4.3.6 owns the deterministic loop that invokes prepared batches sequentially,
merges each completed batch's reference delta, and proceeds to later ingestion
states.

In particular, Task 4.3.6 must deliver the workflow cursor required when a
resolution batch invokes `ClarificationState` and pauses for user input. That
cursor retains the active batch, completed batch results, remaining batches,
and shared reference context. After the clarification child and resolution
state resume, the workflow continues with the remaining batches before moving
to memory/context work. The `ingest_memory` workflow tool must propagate that
pause and eventual completion without converting it into an error or final
assistant response.

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

- Depends on the approved state order, Task 4.3.2 candidate handoff, and Task
  4.3.2a graph-topology alignment.
- Pull in only the deterministic graph capability or child-state tool required
  by this state's agreed behavior; do not wait for Wave 3 as a whole.
- Reference rendering uses the accepted verbosity and owner conventions.
- Node DTO fields correspond explicitly to graph properties.
- Candidate batches follow the configured deterministic policy and expose the
  ordered batch plan required by Task 4.3.6.
- Per-batch identity preparation uses the shared reference context and is
  callable immediately before each invocation; Task 4.3.6 owns that sequential
  execution timing.
- Create and update variants are explicit per node subtype. Update nulls mean
  unchanged, aliases are additive, and clearing fields is outside this task.
- A tool validation/write error returns an explanatory tool result; it does not
  deterministically terminate the whole model interaction.
- The state may return an ordinary external-input continuation from its
  clarification tool. Persisting the enclosing workflow cursor and resuming
  remaining batches is explicitly accepted work in Task 4.3.6.
