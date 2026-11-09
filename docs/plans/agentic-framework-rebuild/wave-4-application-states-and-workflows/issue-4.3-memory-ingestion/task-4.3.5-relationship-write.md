# Task 4.3.5 — write relationships from resolved endpoints

**Status: Not started**

## User story

As the ingestion workflow, I want relationship proposals grounded in the
provided input and written only after their endpoints resolve, so meaningful
relationships are represented without inventing participants.

## What and why

Implement `RelationshipWriteState` as the final write state. This task owns
durable graph relationships, `RelationshipContext`, and the relationship-state
history needed to represent changes over time. Define their typed input/output,
allowed relationship data, prompt guidance, deterministic write functions,
graph-tool mappings, clarification capability, and workflow handoff together.
Execute writes against resolved local endpoint refs. Preserve failed writes as
recoverable tool outputs; reconciliation of missing edges remains outside scope
unless separately prioritized.

The task must wire relationship context end to end: accept resolved participant
refs and relevant `MemoryLog` refs from Task 4.3.4; create or select the
relationship context before writing dependent relationship-state/history links;
bind every created context to the shared `ReferenceContext`; and return readable
context and relationship outcomes to the workflow. It must define explicitly
whether a new observation creates a new relationship-state record or updates
only the current durable edge, without silently flattening history.

The state uses one main LLM/tool session with no separate framework
reasoning/planning stage.

The functional meaning and lifecycle of direct edges, `RelationshipContext`,
and `RelationshipState` are owned by the canonical
[relationship model](../../../../network/relationship-model.md). This task
implements that model without redefining it in state prompts or tool code.

## Where

- Relationship-write state/prompt under `product.application.states.ingestion`.
- Typed graph relationship DTO and write tool under `product.application`.

## Functional communication boundary

Input includes inherited history, reasoning, memory/perception outcomes,
resolved endpoint local refs, and relevant memory refs. A completed write
returns the functional relationship/context result and readable summary;
backend IDs remain internal.

## Dependencies and acceptance

- Depends on earlier states resolving the required endpoints and creating the
  relevant MemoryLog and Perception objects. This state creates or reuses its
  own relationship contexts.
- Allowed relationship schema matches the graph's supported kinds.
- Each endpoint resolves to an existing/created object before the write call.
- Relationship-context creation precedes every dependent relationship-state or
  memory-context link, and all of them use the same run-scoped references.
- DTOs and tools explicitly cover creation versus update of durable edges,
  relationship contexts, and relationship-state history without an untyped
  property bag.
- No relationship omission is silently reported as successful creation.

## Delivery slices

1. **Topology and contracts:** define the semantic provider-facing relationship
   enum and endpoint compatibility, plus explicit direct-edge create/update,
   context create/reuse, and state-append DTOs. Keep backend structural edges
   out of model-facing schemas.
2. **Lookup and persistence:** add owner-scoped exact relationship/context
   lookup, direct-edge upsert/update, context reuse/creation, state append, and
   MemoryLog-to-context linking. Provider refs resolve to backend UUIDs only in
   deterministic handlers.
3. **State and tools:** implement `RelationshipWriteState`, its versioned prompt,
   result DTO, toolbox, clarification option, and normal provider continuation.
   A context-dependent state append occurs only after a context tool output has
   supplied the usable ref.
4. **Consumption contract:** expose repository/service reads for a context with
   participants, relevant memory logs, and chronologically ordered states, plus
   a bounded projection suitable for retrieval. Do not build frontend rendering
   in this task.
5. **Configuration and verification:** expose the actual state configuration in
   the local inspector and test edge reuse, context reuse, initial-state policy,
   append-only enhancement, local/backend reference separation, and compact
   consumption packets.

## Initialization and enhancement acceptance

- The LLM state decides whether the source supports a direct edge, context,
  state, any combination, or only MemoryLog involvement; backend co-occurrence
  never creates a semantic relationship by itself.
- A context is owner-scoped and matched by participant set plus normalized
  category. Exact lookup supplies evidence/reuse; it does not merge a materially
  different relationship.
- An initial state is created only when the source contains meaningful status,
  closeness, emotional, or temporal state information.
- Later observations append states. They do not overwrite history or infer an
  end date for the previous state.
- Repeated identical direct edges, contexts, or state observations do not create
  duplicates.
- Direct relationships remain the ordinary traversal representation. Context
  detail and retrieval hydrate bounded narrative and temporal history according
  to the canonical relationship model.
