# Reference Coherence and Recoverable Structured Validation

## Goal

Make model-facing local references easy to understand and consistent across an
ingestion run, without making their spelling a brittle source of failures. A
structured-output validation error must become feedback for the agent to repair
its response, not an immediate ingestion failure.

## Product and architecture policy

- A local ref is an opaque, run-scoped handle. Its spelling has no business
  meaning and it is never a database UUID.
- Prefer readable conventions such as `node_0001`, `node_existing_lorenzo`,
  `node_new_lorenzo`, `memory_0001`, `memory_new_barbecue`, and
  `context_new_perception`.
- Existing refs supplied in the active context should be copied exactly when
  referring to the same object. New refs should be unique and reused
  consistently throughout the response.
- The same ref must not identify two different objects. Backend UUID mapping
  remains deterministic and backend-owned.
- Naming style is guidance, not identity resolution. Coherence and resolvability
  matter; a valid alternative name must not fail only because it uses another
  readable suffix or existing/new convention.

## Delivery waves

### Wave 0: Contract and message design

- Add clear `Field(description=...)` guidance to every model-facing ref field:
  planned refs, resolved refs, relationship endpoints, host/involved/context
  refs, clarification refs, and write-action refs.
- Explain existing versus new refs, exact reuse of known refs, uniqueness, and
  the prohibition on backend UUIDs in the model-facing output.
- Define a human-readable validation-error format containing the field path,
  what was received, why it is a problem, and the available correction.

### Wave 1: Relax structural validation

- Keep only basic ref validation in Pydantic: non-empty, bounded, safe local
  token, and object-kind compatibility where it is unambiguous.
- Remove naming-pattern checks that reject otherwise coherent names such as
  `node_existing_*`.
- Keep semantic checks at the context/backend boundary: known or newly proposed
  refs, one ref-to-one object identity, correct object kind, and UUID binding.
- Do not silently guess a mapping for an unknown ref. Return a repairable issue.

### Wave 2: Generic validation repair loop

- Extend the shared structured-output runner so every recoverable Pydantic
  validation error appends a `role=user` message to the agent-specific history.
- The message must include the human-readable errors, the previous response
  context, and concise repair instructions; the model must return only the
  requested structured output.
- Allow a small configurable number of repair attempts rather than a single
  hard-coded attempt. Preserve the complete repair history for tracing.
- Keep provider-generated tool-call IDs unchanged; this repair path is a normal
  model turn and must not invent tool identifiers.

### Wave 3: Coverage and cleanup

- Add tests for alternative readable ref names, repeated stories with existing
  graph matches, unknown refs, wrong-kind refs, duplicate refs, and successful
  repair after a validation error.
- Add an end-to-end test proving that an invalid first plan is repaired and then
  reaches resolution/write or clarification as appropriate.
- Update the canonical reference-context plan, prompts, architecture notes, and
  trace diagnostics to describe the recoverable behavior.
- Remove the old one-attempt wording, raw Pydantic-only error formatting, and
  any duplicate ref validation rules left in lower-level packages.

## Expected affected areas

- `src/my_digital_brain/agentic/contexts.py`
- `src/my_digital_brain/agentic/refs.py`
- `src/my_digital_brain/ai/session/runner.py`
- `src/my_digital_brain/ingestion/contracts/`
- `src/my_digital_brain/ingestion/validation.py`
- `src/my_digital_brain/prompts/active.py`
- structured-output, ingestion, and clarification tests
- `docs/architecture/` and `docs/dev-plans/13-canonical-reference-context.md`

## Completion criteria

- The model receives explicit field-level instructions about ref semantics.
- Readable naming variations do not fail solely because of their spelling.
- Every unknown or incoherent ref produces a clear `role=user` repair message.
- Recoverable validation errors are retried automatically and visibly in the
  agent trace.
- Repeated stories reuse resolvable existing refs or follow the clarification /
  idempotency policy; they do not fail merely because the graph already contains
  related nodes.
- No legacy strict naming path or duplicated validation policy remains active.
