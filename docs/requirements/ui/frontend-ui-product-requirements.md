# Frontend Product Requirements

## Purpose

The frontend is the owner's private workspace for capturing memories, asking
questions, and inspecting the resulting knowledge graph. It is not a public
marketing site or a database administration console.

The UI should feel personal without decoration, calm and functional, and clear
about evidence and uncertainty. The chat is an interaction surface; the memory
network is the durable product. The interface connects the two.

## Main workspaces

The product has three primary workspaces:

1. **Chat** for memory capture, questions, corrections, and clarification.
2. **Memory Graph** for finding and inspecting focused graph neighborhoods.
3. **Graph Analytics** for an overview of graph size, coverage, and health.

Entity details, evidence, timeline, map, and graph changes are reached from the
relevant workspace rather than treated as unrelated top-level products.

## Navigation

- Provide persistent navigation among the three workspaces.
- Provide global search for graph entities and a way to open a selected entity
  from chat evidence.
- Let the owner ask about a selected graph entity from its detail view.
- Support direct links to selected graph views without displaying internal
  database identifiers as user-facing labels.
- Adapt the workspace layout to desktop, tablet, and mobile screens.

Detailed workspace requirements live in [Chat](chat-workspace.md), [Memory
Graph](memory-graph-workspace.md), and [Analytics and shared
experience](analytics-and-shared-experience.md). Visual tokens and brand
direction are maintained in [Design](DESIGN.md).

## MVP scope

The first usable frontend must allow the owner to:

- use web chat to capture a memory, ask about stored memory, and answer a
  clarification;
- search the graph and inspect a focused neighborhood and selected entity;
- inspect supporting evidence and navigate to it from chat;
- access a timeline and map for relevant graph context;
- see a basic analytics summary; and
- understand loading, empty, clarification, and error states.

Each workspace document defines its own functional acceptance details. API
routes, payload field names, and backend implementation choices are not defined
here.

## Out of scope for the MVP

- Public marketing pages, multi-tenant administration, and billing.
- Arbitrary raw database administration or rendering the entire graph by
  default.
- Full manual graph editing and merge/split/revert workflows.
- Complex media galleries beyond inspecting available evidence.
- A general structured-query builder unless separately prioritized.

## Success criteria

The frontend is useful when the owner can move naturally from capturing or
asking about a memory to inspecting its graph context and evidence, while
understanding what is uncertain without being overwhelmed by technical detail.
