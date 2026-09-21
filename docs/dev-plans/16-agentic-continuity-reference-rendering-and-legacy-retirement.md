# Agentic Continuity, Reference Rendering, and Legacy Retirement

## Goal

Make the active agentic runtime a single, continuous tool-calling system:

```text
agent frame -> tool request -> tool processing -> tool output -> invoking agent response
```

The sequence is identical when a tool fails. A failure is informative tool
output for the invoking agent, not a deterministic runtime exit. At the same
time, every agent must receive a compact, human-readable inventory of the
model-facing refs already known, planned, or created in the current flow.

This plan also retires the superseded `IngestionService` pipeline and its
parallel reference registry. The MVP must have one active ingestion path and
one model-facing reference contract.

## Confirmed pain points

### P1 — Deterministic runtime exits bypass agent recovery

`MemoryIngestionRuntimeService` currently converts a child/action error into a
failed phase result. This can stop the parent orchestration before the caller
has received the tool error as normal conversational context. In the observed
run, that contributed to a generic final chat reply after an ingestion error.

**Target solution.** Preserve the frame and append exactly one structured tool
output for the provider-issued `tool_call_id`. The same invoking agent receives
the error and decides whether to retry with corrected arguments, re-plan,
clarify, defer an affected fact, or explain the outcome. The runtime records
status for traces, but does not invent a semantic stop decision.

### P2 — References are propagated as JSON but not rendered as an explicit inventory

The active node, memory, and edge prompts receive `RefContext.model_facing_packet()`
under `Known refs`. It includes a ref, kind, name/summary, and resolution
status, but is supplied as JSON and does not explicitly tell the model how the
reference should be reused.

**Target solution.** Keep `RefContext` as the one small reference class and
add a simple `render_prompt_inventory()` method. It renders only model-facing
information, for example:

```text
Known objects in this ingestion:
- `node_new_jacopo_brutti` refers to the Person "Jacopo Brutti".
  It was created earlier in this ingestion; reuse this exact ref for the same person.
- `memory_new_mare` refers to the MemoryLog "Mare e Bang Duel".
  It is planned and is not created yet.
```

No backend UUID, database alias, or technical implementation detail is exposed
to the model. Structured packets remain available where a schema needs them;
the rendered inventory is the prompt-readable explanation of their meaning.

### P3 — The active codebase contains a superseded ingestion pipeline and two ref systems

Web chat no longer invokes `IngestionService`, but the old pipeline remains for
an old UAT script and old tests. Some active graph, RAG, API, and clarification
code still imports contracts or `RunReferenceRegistry` from the old
`ingestion` package. That leaves the active `RefContext` beside an older
reference vocabulary and makes ownership unclear.

**Target solution.** Migrate the genuinely active graph/RAG/clarification
primitives into their proper active packages, replace active
`RunReferenceRegistry` use with `RefContext`, then remove the old
`IngestionService` pipeline, its UAT helpers, tests, prompts, contracts, and
documentation. Do not retain adapters, aliases, compatibility imports, or
parallel registries.

### P4 — Explicit durable relationships are under-planned

The recent story explicitly described Elena Pollastrelli and Matteo Morichetti
as partners, but the edge planner emitted no relationship action. The model
did not call a relationship tool, so this was a reasoning/planning omission,
not a rejected graph-write contract.

**Target solution.** Add short behavioural standards to the active planning
prompts: capture clearly stated ongoing relationships between identified
entities; do not infer one from co-presence; ask only when the identity,
endpoint, direction, or meaning is genuinely ambiguous. The typed edge
contracts remain the source of the exact allowed relationship representation.

## Non-negotiable guidelines

- A tool output is unique only by the provider-issued OpenAI `tool_call_id`.
  Do not deduplicate by tool name, arguments, text, or a locally generated ID.
- A repeated `tool_call_id` reuses its persisted output and is never executed
  or appended again. Distinct call IDs remain distinct calls.
- Tool error, success, and clarification outcomes always return to the
  invoking agent frame. The normal chat response is authored only after that
  frame has the tool output.
- Runtime status is operational observability, not a deterministic semantic
  decision to stop an agent. The agent is given the informative error and
  chooses the next appropriate action when it can.
- A model-facing local ref is a run-scoped handle, never a database UUID and
  never a business identity.
- Reusing the same ref for the same planned object is mandatory. The backend
  must bind successful writes back to that ref before later steps see context.
- Do not block a create merely because two different planned refs have the
  same displayed name. The model makes the semantic identity decision from
  the complete rendered context; the backend only preserves coherent bindings
  and validates contracts.
- `RefContext` is the sole active model-facing reference authority. There is
  no registry conversion or legacy compatibility path.
- Prompts provide behavioural guidance; Pydantic models and typed tools define
  the exact objects and fields the backend accepts.
- Retire obsolete code fully after migration. Do not leave unused packages,
  scripts, tests, prompt mappings, or documentation behind.

## Delivery tasks

### Wave 1 — Continuous tool-result transport

1. Replace deterministic failed-phase returns in the active agentic runtime
   with a normal error `ToolResult` delivery to the invoking frame.
2. Persist and look up tool outputs by provider `tool_call_id`; guarantee one
   provider `role: tool` message and one execution per call ID.
3. Remove generic post-tool fallback replies. After any tool output, invoke the
   caller's normal continuation; only provider/infrastructure failure may use
   a concise application-level failure response.
4. Update tests that currently assert ingestion stops after a required phase
   error. Add success, error/retry, error/clarification, error/defer, and
   nested-agent-as-tool cases.

### Wave 2 — Reference-context rendering and propagation proof

1. Add `RefContext.render_prompt_inventory()` with plain, compact lines for
   existing, planned, created, updated, and unresolved refs.
2. Render that inventory in every active state that reasons, plans, executes a
   write, resumes a clarification, or plans edges. Keep structured ref packets
   only where structured data is required.
3. Verify a single `RefContext` instance/snapshot flows through reasoning,
   nodes, memory logs, edges, nested tools, persisted frames, and resume.
4. Add the exact regression scenario: create `node_new_jacopo_brutti` in one
   child action, then ensure a later sibling action receives its bound, readable
   ref and can link it without treating it as unresolved.
5. Add a separate cross-run identity scenario proving the model can choose to
   reuse an existing candidate or intentionally create a differently scoped
   entity with the same display name.

### Wave 3 — Relationship planning standards

1. Add concise behavioural standards and broad examples for explicit durable
   relationships to the reasoning/node/edge planning prompts.
2. Ensure the reasoning packet carries explicit relationship evidence into edge
   planning and that the edge planner receives the rendered ref inventory.
3. Add regression cases for an explicit relationship, co-presence only, and an
   ambiguous endpoint requiring clarification. Verify only the explicit case
   emits the typed relationship tool call.

### Wave 4 — Retire the old ingestion pipeline

1. Inventory every non-legacy consumer of `src/my_digital_brain/ingestion/`.
   Classify each imported item as graph, RAG, clarification, API, or obsolete.
2. Move active shared primitives to their owning active packages and update all
   imports. In particular, replace `RunReferenceRegistry` use in graph-context
   building with `RefContext`.
3. Replace the old UAT scripts with active-agentic runtime tests or remove them
   if their coverage is duplicated.
4. Delete `IngestionService`, the old pipeline implementation, unused
   contracts, prompts, scripts, tests, compiled artefacts, and docs after the
   dependency graph is empty.
5. Run the full relevant test suite, static import search, and an end-to-end
   local ingestion run before declaring retirement complete.

## Affected files and areas

### Active runtime and prompts

- `src/my_digital_brain/agentic/runtime_memory.py`
- `src/my_digital_brain/agentic/runtime.py`
- `src/my_digital_brain/agentic/refs.py`
- `src/my_digital_brain/agentic/contexts.py`
- `src/my_digital_brain/agentic/history.py`
- `src/my_digital_brain/agentic/tools/bindings.py`
- `src/my_digital_brain/prompts/active.py`
- agentic runtime, tool-loop, reference-context, and chat integration tests

### Legacy retirement and migration

- `src/my_digital_brain/graph/context_package.py`
- `src/my_digital_brain/clarification/context_projection.py`
- `src/my_digital_brain/clarification/toolbox.py`
- `src/my_digital_brain/rag/`
- `src/my_digital_brain/api/routes/graph.py`
- `src/my_digital_brain/ingestion/` — removed once active consumers are migrated
- `scripts/uat_refined_trace_common.py` and dependent UAT scripts — replaced or removed
- legacy ingestion tests and docs — removed or migrated with the active flow

## Completion criteria

- A failed tool call appears once, with its original OpenAI `tool_call_id`, and
  the same invoking agent produces the next response.
- A tool output cannot become a raw final chat message or trigger a generic
  greeting/fallback after a real user action.
- Every active model state can read a compact inventory explaining exactly what
  each local ref represents and whether it is already created.
- The Jacopo sibling-action regression shows one coherent bound ref through
  the active UI/runtime path.
- Explicit relationship evidence creates the appropriate typed edge action;
  co-presence alone does not.
- No production or developer workflow imports or runs `IngestionService`,
  `RunReferenceRegistry`, or the old ingestion pipeline after migration.
- `rg` confirms no obsolete compatibility imports, mappings, scripts, or docs
  remain.

## Relationship to earlier plans

This plan refines the reference work in plans 13–14 and supersedes the
deterministic stop-on-error direction in plan 15. The objective is not to hide
errors or claim success after incomplete work: it is to return every error to
the invoking agent so that the flow remains agentic, traceable, and honest.
