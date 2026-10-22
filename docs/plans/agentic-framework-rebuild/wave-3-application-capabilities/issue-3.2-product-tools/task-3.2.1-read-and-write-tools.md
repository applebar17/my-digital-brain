# Task 3.2.1 — define retrieval and graph tool bindings

**Status: Not started**

## User story

As a state, I want explicit read/write tools backed by typed graph and retrieval
services, so tool selection can be agentic while the actual data operation
remains deterministic.

## What and why

Define product DTOs and bindings for the capabilities required by the initial
query and ingestion states. Generate provider schemas from their annotated DTOs
through the generic tool layer; avoid manually duplicated JSON schemas.

For graph writes, keep the model-facing operation surface small: use one
registered graph-action function mapped to one dispatcher, with a typed union
of concrete action DTO variants. Variants fix valid operation/kind/type
combinations and provide explicit fields for that graph object and operation.
Do not register one provider function per node subtype, and do not replace
typed fields with a generic property or metadata dictionary. The canonical
DTO, variant rules, and runtime filtering behavior are specified in the
[tool definition and toolbox contract](../../../../ai-engineering/contracts/tool-definition-and-toolbox.md#typed-graph-action-tool-pattern).

## Where

- `src/product/application/tools/` typed registrations and service bindings.
- State-specific toolbox composition in `product.application.states`.

## Functional communication DTOs

Read inputs express a query, target local ref, or context scope; outputs return
readable records/evidence and uncertainty. A graph write action carries its
operation, graph kind, type, local ref/endpoints, and the corresponding typed
fields. Planning may reuse the same action DTO variants in an ordered plan;
runtime toolbox composition selects only predeclared variants allowed by the
state, with a validated plan narrowing but never widening that allowlist.
Backend UUIDs remain behind the deterministic service boundary.

MemoryLog uses a dedicated typed memory-action variant with title, log text,
and local host/involved/context refs. Relationship types exposed to a state
must be aligned with the graph contract; structural links owned by object
creation are not free-standing model-selected writes. Create and update use
distinct variants. Delete is excluded until its object-specific lifecycle is
defined. Successful outputs carry the functional result and relevant local
refs, not backend IDs.

## Dependencies and acceptance

- Depends on Tasks 2.1.1–2.1.2 and 3.1.1–3.1.2.
- Every concrete action variant has explicit field meanings and maps to one
  deterministic service operation.
- One graph-action provider function maps to one dispatcher; the runtime
  toolbox filters its typed action variants from the state allowlist and
  validated plan.
- The provider schema contains only selected variants and passes the chosen
  adapter's strict-schema compatibility checks.
- Each tool has one success DTO and defined error result semantics.
- Node/context/relationship tool availability is explicit per state.
- No arbitrary property bag, backend UUID, or duplicate per-type provider
  function surface is introduced.
