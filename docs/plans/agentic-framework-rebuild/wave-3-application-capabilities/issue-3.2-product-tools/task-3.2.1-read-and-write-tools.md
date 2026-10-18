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

## Where

- `src/product/application/tools/` typed registrations and service bindings.
- State-specific toolbox composition in `product.application.states`.

## Functional communication DTOs

Read inputs express a query, target local ref, or context scope; outputs return
readable records/evidence and uncertainty. Write inputs express a typed graph
object and local endpoint refs; outputs return created/updated local refs and a
functional outcome. Backend UUIDs stay in the reference map.

## Dependencies and acceptance

- Depends on Tasks 2.1.1–2.1.2 and 3.1.1–3.1.2.
- Every exposed field has explicit meaning and maps to service input.
- Each tool has one success DTO and defined error result semantics.
- Node/context/relationship tool availability is explicit per state.
