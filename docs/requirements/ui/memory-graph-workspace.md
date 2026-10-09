# Memory Graph Workspace Requirements

## Purpose

The Memory Graph workspace lets the owner search, inspect, and navigate a
focused portion of the memory network. It must not render the entire graph by
default or require the owner to understand database internals.

## Workspace layout

On desktop, provide search and filters, a central graph or graph/list view, and
a detail inspector for the selected node or relationship. Evidence, timeline,
map, changes, and contradictions may appear as tabs, drawers, or a secondary
panel. On smaller screens, keep these tasks available through focused screens
and drawers.

## Search and focused graph

The owner can search by text, select a result as the graph focus, and filter by
available node type, lifecycle, privacy, or trust attributes. The graph
supports a bounded neighborhood with a controllable depth and result limit.

Selecting a node focuses the view on that node and its directly connected
neighbors; unrelated nodes disappear from the focused view. Returning to the
prior graph view restores its previous contents and focus. The owner can also
expand from a selected node, collapse or refocus, pan, zoom, fit, and reset the
view. Labels remain readable at normal zoom. A list or table fallback is
available when the graph is too dense or unavailable.

The default view is a useful focused neighborhood, not the full database.
Backend routes and query parameters are owned by the API contracts, not this
product requirement.

## Visual encoding

Use restrained visual cues to distinguish node type, selected focus,
relationship type and direction, and available lifecycle, privacy, trust, or
uncertainty information. Keep the view legible; the goal is inspection, not
decorative network art.

## Node and relationship details

Selecting a node opens a detail view with its human-readable title, type,
description, key available properties, lifecycle and trust context, and
relationships. Where present, it also provides perceptions, relationship
context, source evidence, changes, contradictions, and merge history. Raw
metadata is secondary detail, not the default presentation. Technical database
identifiers must not replace names or titles in the user-facing graph.

Selecting a relationship shows its type, endpoints, direction, description,
and available lifecycle, trust, temporal, emotional, and source context. A
relationship context may also show how its state changed over time.

## Evidence, timeline, and map

Evidence is reachable from chat, node and relationship details, timeline items,
and map items. It can show source type and channel, relevant times, a source
summary or transcript reference, linked memory context, provenance, trust, and
privacy when available. Identifiers may be available in advanced diagnostics
but must not dominate ordinary presentation.

The timeline supports memories associated with a selected node, date-range
filtering, available time basis and precision, detail navigation, and evidence
inspection. The map supports exploration of place-linked memories, location and
date filtering, selecting a result to inspect its graph context, and useful
handling of places without exact coordinates.

The canonical meanings of nodes, relationships, evidence, time, and affective
context are defined in the [network documentation](../../network/README.md).

## Correction boundary

The initial graph experience may be read-heavy. It can expose supported actions
such as asking chat about a selected node, proposing a correction through chat,
opening evidence, or inspecting contradictions and merge history. Direct graph
editing, merge, split, and revert capabilities are not required for the MVP.
Any supported mutation must be explicit and require confirmation appropriate
to its impact. Detailed future correction behavior is in [memory maintenance
and corrections](../functional/memory-maintenance-and-corrections.md).

## Acceptance checks

- Search opens a focused, bounded graph view and selection shows useful detail.
- Focusing a node hides unrelated nodes; returning restores the previous view.
- Evidence is reachable from the places where it is referenced.
- Timeline and map provide navigation back to the relevant graph context.
- Missing optional data and dense or unavailable graph results have usable
  fallback states.
- Normal graph labels show human-readable names, not technical identifiers.
