# Ingestion Execution Integrity: Failure Analysis and Recovery Plan

## Purpose

This document records the observed end-to-end ingestion failure from the
latest local test run, separates confirmed evidence from implementation
hypotheses, and defines the smallest clean path to a reliable user outcome.
It follows the reference-coherence policy in
`14-reference-coherence-and-recoverable-validation.md`: local model refs are
valid only when the backend can resolve them to the current durable graph.

## Observed run

- Chat session: `d8345000-de68-4d34-8c8c-df5bfeca4a0c`.
- Input: the recurring Italian barbecue / beach story used for ingestion
  testing, after graph nodes had been reset.
- User-visible result: people and social circles appeared with good names;
  there were no MemoryLogs, very few/no meaningful edges, no clarification
  question, and the chat nevertheless confirmed that the memory was saved.
- Trace evidence: the parent `memory_ingestion` frame was completed, while
  its nested `memory_creation` frame failed.

## Executive assessment

The model's planning was materially better than the stored result. It planned
five titled memory atoms, identified identity/location ambiguities, and
produced useful entity summaries. The failures occurred while translating that
plan into backend-owned graph operations and while propagating their outcomes.

This is not primarily a model-quality or frontend-rendering failure. The
backend currently permits an execution failure to be followed by later phases
and then emits a successful terminal result. That breaks the fundamental
contract: a success response must mean that every required durable operation
completed, or that the run intentionally paused for clarification.

## Confirmed failure points

### F1 — Stale owner reference after graph reset

**Evidence.** The graph contained the configured owner `person:owner`, while
the active reference context resolved `OWNER` to `owner-local`. The first
`create_memory_log` attempted to use `owner-local` and failed with `Graph node
not found: owner-local`.

**Functional impact.** First-person memories cannot be attached to their
owner. The user sees entity extraction succeed but the actual memory is absent.

**Technical failure point.** `OwnerNodeManager` deliberately treats
`Settings.owner_graph_node_id` as canonical
([`graph/owner.py`](../../src/my_digital_brain/graph/owner.py)); however, a
run-scoped ref context can retain a previous backend binding. The graph reset
invalidated that binding without invalidating or rebuilding the reference
context used by child frames.

**Proposed fix.** Establish one owner-binding invariant at ingestion start:

- resolve an authenticated application user into a request-scoped owner context
  before the initial reference packet is built;
- bind `OWNER` only from that context's current graph-owner ID;
- validate every existing ref binding against the graph before a mutation;
- when a reset/missing-node condition is detected, discard the stale binding,
  rebuild the trusted owner entry, and retry only the affected operation;
- do not retain `owner-local` or any alternate backend owner identity.

The local `OWNER` alias remains model-facing; the graph-owner ID remains solely
backend-owned. The present configured owner is the local development resolver;
deployment must provide an authenticated resolver that selects the requesting
user's owner Person node.

**Acceptance criteria.** After deleting graph nodes and restarting the local
application, a first-person ingestion creates/reuses the canonical owner and
creates its MemoryLog without manual repair.

### F2 — A failed child write is converted into a completed ingestion

**Evidence.** The initial `create_memory_log` failure was followed by attempts
with no resolved host, which returned `MemoryLog creation requires at least one
host target.` The persisted chat response still said, in effect, that the
memory had been stored. The parent frame was marked completed.

**Technical failure point.** In
[`agentic/runtime_memory.py`](../../src/my_digital_brain/agentic/runtime_memory.py),
`_execute_memory_plan_actions()` calculates an `error` status when a child
returns an error. In `run()`, the callers only stop on `interrupted` or
`pending`; they do not return on `error`. Execution consequently reaches the
unconditional final `MemoryIngestionResultContext(status="ok")` path.

**Functional impact.** The UI and stored chat history make a false completion
claim. It also makes testing misleading: a sparse graph looks like an
extraction-quality issue rather than a failed transaction.

**Proposed fix.** Make action outcomes explicit and terminal at the orchestration
boundary:

- return immediately on a non-recoverable child error; do not plan or execute
  later phases from a failed prerequisite;
- for a recoverable write/ref error, create a structured repair/resume state
  with the failed action, safe diagnostic, and current ref packet; retry only
  after backend repair or model correction;
- construct final user-facing completion text from verified write receipts
  (created/updated IDs and counts), never from a planning summary;
- mark a parent frame `failed` or `interrupted`, never `completed`, when any
  required child operation has that status;
- remove the unconditional success finalizer rather than keeping it as a
  fallback path.

**Acceptance criteria.** A forced `create_memory_log` failure produces no
success message, records an actionable trace error, and prevents the edge
phase. A successful response is impossible unless the required write receipts
are present.

### F3 — Clarification candidates are informational only

**Evidence.** The reasoning/planning trace included questions about the
barbecue location, several incomplete identities, an ambiguous plural
reference, and an unclear relationship direction. No `ask_clarification`
tool call was emitted, so the frontend had no question packet to render.

**Technical failure point.** `MemoryIngestionReasoning` accepts
`missing_context_questions` and planning contracts accept `context_gaps`, but
the memory-planning pipeline carries them as descriptive data. It does not
apply a deterministic policy that converts material gaps into the existing
`ask_clarification` runtime interruption. The resolution agent itself already
supports the tool and instructs the model to use it
([`ingestion/resolution_agent.py`](../../src/my_digital_brain/ingestion/resolution_agent.py)).

**Functional impact.** The system either silently saves an under-specified
memory or fails downstream, instead of asking a concise human question at the
moment it matters. The absence of the question component in this run is a
backend decision failure, not a frontend integration failure.

**Proposed fix.** Add one shared escalation policy between planning and writes:

- classify each gap as `non_blocking`, `clarify_before_write`, or
  `defer_affected_fact`;
- require `ask_clarification` before a write when identity, primary host, or
  event/place identity would make the new fact unsafe or non-resumable;
- use a human-facing question generated by the clarification agent, with only
  the minimum context and one answerable choice/request;
- allow non-blocking details to be saved as explicitly uncertain instead of
  blocking the whole story;
- preserve the clarification as a real tool interruption and resume through
  its provider-issued tool-call ID.

**Acceptance criteria.** The test story produces a question for a material
identity/location ambiguity; answering it resumes the same run and the answer
is applied to the planned structured payload before writes.

### F4 — Relationship planning lacks the resolved handoff packet

**Evidence.** The edge-planning trace reported that node/memory plan packets
or known refs were unavailable and declined to create durable relationships.
The resulting graph contains entities but lacks the relationships the model
had identified.

**Technical failure point.** The phase runner registers planned refs, but the
edge phase needs the *resolved and successfully written* node and MemoryLog
refs, not just proposed local refs. When memory creation failed, no valid
MemoryLog refs existed; the pipeline nevertheless continued to the edge phase.
The phase inputs in `runtime_memory.py` expose plan packets, but the durable
write outcome is not a required, coherent phase handoff contract.

**Implemented direction.** Keep one canonical `RefContext`: creation actions
must name their planned output ref; successful child writes must bind that ref
to its backend object before the next phase; edge planning treats the current
known-refs packet as execution authority. An edge whose endpoint remains
unresolved is deferred without rolling back completed nodes or MemoryLogs.
Durable retry/recovery of those deferred edges remains a separate follow-up.

**Functional impact.** The graph is structurally incomplete even when entity
names are correct. This makes the graph view seem to have a rendering problem
when its source data has no edges to render.

**Proposed fix.** Define a single immutable `ExecutionReceipt` packet per
phase, containing only backend-confirmed local-ref-to-graph-ID bindings and
created/updated relationship context refs. Feed it into the next phase:

- edge planning runs only after node and MemoryLog receipts are successful;
- it receives the combined canonical reference context plus receipts;
- an absent prerequisite makes the phase failed/interrupted, never a best
  effort empty-edge pass;
- do not duplicate a second ad-hoc ref map; extend the canonical ref context
  from plan 13/14 with backend confirmations.

**Acceptance criteria.** A successful story with five MemoryLogs produces
their host/involvement edges and the supported inter-entity relationships. A
failed memory phase results in zero edge attempts.

### F5 — Planned entity descriptions do not reach durable node presentation

**Evidence.** Node planning contained useful person summaries, but the stored
graph node presentation has names and little/no summary. `CandidateEntity`
supports an optional `description`, while the UI reads backend-owned
presentation fields.

**Technical failure point.** The entity-plan/ref-packet summary and the
candidate-to-graph write contract are not reliably mapped to one durable
description field. This loses valuable model output between planning and graph
projection rather than at frontend rendering time.

**Functional impact.** The graph is understandable only as a list of names;
the user cannot tell who a person is or why that node exists.

**Proposed fix.** Make presentation content intentional in the structured and
durable contracts:

- require/strongly guide a concise, source-grounded entity description whenever
  an entity is created or materially updated;
- persist it in the label-approved graph property used by the central
  `GraphNodePresentation.summary` mapper;
- retain the planner summary only as a fallback when the candidate description
  is absent and its source/provenance is equivalent;
- validate a blank/placeholder description as repairable structured-output
  feedback where a description is required by the node type.

**Acceptance criteria.** Newly created people from the test story have a
human-readable title and a short description in both graph search/projection
and the node inspector, without frontend reconstruction of raw properties.

### F6 — Operational trace is not sufficient for human diagnosis

**Evidence.** This diagnosis required direct SQLite inspection of persisted
`chat_agentic_frames`; local JSONL/application logs did not expose the nested
failure in a readable way. The trace page already has a dev-only role but did
not make the failed child, parent completion, or actionable error legible.

**Functional impact.** A tester receives a generic success/failure message and
cannot distinguish model reasoning, a clarification wait, a validation repair,
and an infrastructure/write failure.

**Proposed fix.** Treat persisted agentic frames as the source for the dev
trace and render a compact execution tree: phase, outcome, child operation,
safe error, retry/repair status, and write receipts. Add structured application
logs for each frame transition, correlated by chat session and frame/tool-call
IDs. Keep raw backend IDs confined to the dev trace, not the normal chat UI.

**Acceptance criteria.** For this exact failure, the trace page visibly shows:
`memory_creation failed → owner ref missing → parent failed`, with no need for
database inspection.

## Failure sequence

```text
Reasoning inventory
  -> good entity / memory / edge plan and ambiguity signals
  -> node writes mostly succeed
  -> MemoryLog host OWNER resolves to stale owner-local             [F1]
  -> create_memory_log fails; later logs lack a valid host          [F2]
  -> pipeline still starts edge planning without write receipts     [F4]
  -> unconditional terminal result reports success                  [F2]
  -> chat says saved; graph shows only partial entities
```

## Delivery order

### Wave 1 — Execution truthfulness and owner integrity

1. Add the owner binding invariant and regression coverage for graph reset.
2. Stop `memory_ingestion` on child `error`; propagate failed/interrupted
   frames correctly.
3. Derive final completion language from verified execution receipts.
4. Add an integration test that intentionally removes the owner and asserts no
   false successful response.

This wave is the prerequisite for trustworthy end-to-end testing.

### Wave 2 — Clarification and phase handoff

1. Add the material-gap escalation policy to the shared ingestion runtime.
2. Introduce phase execution receipts and pass confirmed refs to edge planning.
3. Cover interruption, answer/resume, and no-edge-after-memory-failure paths.

### Wave 3 — Durable presentation and developer observability

1. Complete the candidate/ref-plan-to-description mapping and validation.
2. Improve the dev trace from persisted frames and add correlated structured
   logs.
3. Re-run the standard story from an empty graph and verify graph projection,
   inspector descriptions, MemoryLogs, edges, clarification behavior, and
   final chat outcome together.

## Files expected to change

- `src/my_digital_brain/agentic/runtime_memory.py`
- `src/my_digital_brain/agentic/runtime.py`
- `src/my_digital_brain/agentic/contexts.py`
- `src/my_digital_brain/agentic/refs.py` and reference-context builders
- `src/my_digital_brain/graph/owner.py`
- `src/my_digital_brain/ingestion/resolution_agent.py`
- `src/my_digital_brain/ingestion/contracts/candidates.py`
- candidate-to-graph persistence/projection services
- agentic runtime, ingestion, graph-owner, API integration, and frontend dev
  trace tests

## Cleanup constraints

- Do not retain any success fallback based on planning completion.
- Do not create a second owner ID or a parallel local-ref mapping.
- Do not make the frontend infer write success or reconstruct entity summaries
  from arbitrary raw properties.
- Do not solve material ambiguities with hidden best-effort writes; use the
  established clarification tool interruption or explicitly defer the affected
  fact.
- Keep provider tool-call IDs intact across nested agent/tool sessions.

## Open product decisions

No blocking decision is needed for Wave 1. Before Wave 2, confirm the desired
threshold for clarification: the proposed default is to ask only when the
answer changes identity, the primary memory host, or a durable event/place;
otherwise save a clearly qualified fact and avoid unnecessary interruptions.
