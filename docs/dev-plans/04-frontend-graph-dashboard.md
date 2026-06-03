# Frontend Graph Visualization Dashboard

## Goal

Define the future frontend that lets the user inspect, search, and visualize the memory graph without turning the product into a heavy admin interface.

Detailed product UI requirements for design and frontend implementation are
defined in
[Frontend UI Product Requirements](../requirements/ui/frontend-ui-product-requirements.md).

## Wave 0: Baseline Decisions

- Frontend comes after the backend memory loop is useful.
- Likely stack: React, Next.js, or similar.
- Dashboard should prioritize inspection, exploration, and correction.
- Graph visualization should show focused neighborhoods, not the entire graph.
- UI should be personal and functional, not public-product marketing.

## Wave 1: MVP Dashboard

Core views:

- Search.
- Entity detail page.
- Source/evidence panel.
- Relationship list.
- Focused graph neighborhood.
- Timeline view.
- Map view.

Entity detail should show:

- Description.
- Type.
- Aliases.
- Relationships.
- Claims.
- Sources.
- Confidence/trust.
- Privacy/lifecycle state.
- Metadata.

## Wave 2: Correction And Exploration

- Merge duplicate entities.
- Split incorrectly merged entities.
- Mark fact wrong, stale, disputed, or confirmed.
- Expire old contact details.
- Inspect profile memories.
- Inspect contradiction reports.
- Expand graph neighborhood interactively.
- Filter by type, time, place, source, confidence, and privacy.

## Wave 3: Advanced Visualization

- Memory clusters.
- Relationship paths between entities.
- Place-based maps with event overlays.
- Time-based animations or timeline clustering.
- Source-centric exploration.
- Graph statistics dashboard.
- Personal memory digest.

## UX Principles

- Do not expose graph complexity unless it helps.
- Keep common tasks one or two actions away.
- Use timeline and map views as first-class memory navigation modes.
- Show provenance without overwhelming the user.
- Make correction easy but not mandatory for every memory.

## Initial Success Criteria

- User can search for an entity.
- User can inspect a memory and its evidence.
- User can view a focused graph neighborhood.
- User can browse memories by timeline.
- User can see place-linked memories on a map.
