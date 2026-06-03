# Frontend UI Product Requirements

## Purpose

Define the frontend product that lets the owner of the brain capture, query,
inspect, and understand their personal memory graph.

This document is written as a brief for UI design and frontend development. It
should guide screen architecture, interaction design, component design, and
implementation planning.

## Product Stance

The frontend is a private memory workspace, not a public landing page and not a
database administration console.

The interface should feel:

- personal, but not decorative;
- calm, compact, and functional;
- optimized for repeated inspection and correction;
- clear about provenance, confidence, privacy, and uncertainty;
- powerful enough for graph exploration without exposing unnecessary database
  complexity.

The chatbot is an input and interrogation layer. The graph is the durable memory
product. The UI must make both feel connected.

## Primary Users

The first user is the owner of the digital brain.

The owner needs to:

- add memories through natural conversation;
- answer clarification questions without leaving the chat flow;
- ask questions about stored memories;
- inspect what the graph knows about a person, event, place, topic, object,
  organization, source, claim, profile memory, or relationship context;
- understand why the system believes something;
- find and correct stale, wrong, ambiguous, private, or contradicted memories;
- see graph health and coverage without reading raw database records.

## Top-Level Product Structure

The first frontend should use three main workspaces:

1. Chat
2. Memory Graph
3. Graph Analytics

Entity detail, source/evidence inspection, timeline, map, contradictions,
changes, and merge history should be available as panels, tabs, drawers, or
routes inside those workspaces.

## Global Navigation Requirements

The frontend must provide:

- persistent navigation between Chat, Memory Graph, and Graph Analytics;
- a global search entry point for finding graph entities;
- deep links to individual graph nodes when the backend returns node ids;
- a way to open graph context from chat evidence references;
- a way to ask a chat question about the currently selected graph node;
- clear active state for the current workspace;
- responsive layouts for desktop and mobile.

The desktop layout can prioritize a multi-pane workspace. Mobile should
collapse to stacked screens, drawers, and focused detail pages.

## View 1: Chat

### Purpose

The chat view lets the user interact with the same conversation runtime used by
Telegram. It must be a first-class product interface, not a debug client.

The chat must support these core workflows:

- store a new memory;
- answer a clarification question;
- ask a question about the graph;
- propose a correction;
- cancel or skip a pending process when appropriate;
- inspect evidence returned with an answer.

### Required Layout

The chat view should include:

- session header with conversation status and pending process status when one
  exists;
- message timeline with user and assistant messages;
- assistant message rendering based primarily on `primary_text`;
- composer for text input;
- future-ready attachment or audio affordance for voice/media;
- pending clarification display when the backend returns `pending_process`;
- evidence side panel or expandable evidence references;
- action buttons when the backend returns `actions`;
- non-intrusive status area for loading, failed requests, cancelled processes,
  and accepted background work.

Diagnostics must not be shown by default. They can be exposed only behind a
developer/debug affordance.

### Backend Contracts

The chat UI should use:

- `POST /chat/messages`
- `GET /chat/sessions/{session_id}`
- `POST /chat/sessions/{session_id}/cancel`

The web chat request payload includes:

- `conversation_id`
- `sender_id`
- `owner_id`
- `message_id`
- `text`
- `media_refs`
- `reply_to_message_id`
- `pending_process_id`
- `conversation_history_refs`
- `received_at`
- `metadata`

The visible assistant message should come from `ChatResponse.primary_text`.
Structured sidecars should support UI behavior:

- `pending_process`: show the active question/context and attach the process id
  to the next relevant message;
- `actions`: render explicit commands, especially confirmation actions;
- `evidence`: render source or graph references that can open the evidence
  drawer or graph detail;
- `diagnostics`: hide unless debugging;
- `status`: show lightweight state such as ok, accepted, needs user input,
  failed, or cancelled.

### Chat Interaction Rules

Clarification questions should feel like normal chat messages. The UI should not
turn them into heavy forms unless the backend returns a clearly structured
action.

If a pending process exists, the composer should preserve normal user freedom.
The user may answer, ask a new question, send a new memory, correct something,
or cancel. The frontend should pass pending context to the backend but must not
decide the business meaning of the next message.

When the assistant response includes evidence, the user should be able to:

- open the source summary;
- jump to the related graph node;
- see whether evidence is user-stated, inferred, enriched, contradicted, or
  stale when the data is available.

When the assistant response includes a correction or mutation action, the UI
should require clear user confirmation before applying it.

## View 2: Memory Graph

### Purpose

The Memory Graph workspace lets the user search, inspect, and navigate focused
graph neighborhoods. It must not attempt to render the entire graph by default.

The graph view should answer:

- What is this memory object?
- How is it connected?
- What evidence supports it?
- What is uncertain, private, stale, contradicted, or inferred?
- What happened over time?
- Where did place-linked memories happen?
- What can be corrected?

### Required Layout

The desktop graph workspace should have:

- left search and filter panel;
- central graph canvas or graph/list hybrid renderer;
- right detail inspector for selected nodes and relationships;
- bottom or tabbed secondary area for timeline, map, evidence, changes, and
  contradictions.

On mobile, the same content should collapse into:

- search screen;
- graph screen;
- selected item detail screen;
- evidence/timeline/map screens.

### Search And Seed Selection

The graph workspace must support:

- search by text query;
- filtering by node label;
- filtering by lifecycle state;
- filtering by privacy level;
- filtering by trust level;
- result limit controls;
- selecting a seed node to render its neighborhood.

Backend entry point:

- `GET /graph/nodes/search`

### Focused Neighborhood Rendering

The graph renderer must support:

- rendering a seed node and its focused neighborhood;
- depth control from 1 to 3;
- result limit control;
- node selection;
- relationship selection;
- expand from selected node;
- collapse or refocus on selected node;
- pan, zoom, fit to view, and reset view;
- readable labels at normal zoom;
- fallback list/table rendering when the graph is too dense or unavailable.

Backend entry points:

- `GET /graph/views/neighborhood`
- `GET /graph/nodes/{node_id}/neighborhood`
- `GET /graph/nodes/{node_id}/memories`

### Visual Encoding Requirements

The visual design should encode:

- node label/type;
- selected seed node;
- lifecycle state;
- privacy level;
- trust level;
- confidence or uncertainty when available;
- contradicted or disputed status when available;
- archived/stale state when included;
- direction and type of relationships.

Use visual encoding sparingly. The graph should remain readable. The primary
goal is inspection, not decorative network art.

### Entity Detail Inspector

Selecting a node should open an entity detail inspector.

The inspector should display:

- title or display name;
- node label/type;
- description;
- aliases or normalized names when present;
- key typed properties;
- lifecycle state;
- privacy level;
- trust level;
- confidence;
- canonical node when this node was merged or archived;
- relationships;
- perceptions and affective context;
- relationship contexts;
- source evidence;
- change history;
- contradiction records;
- merge records;
- raw metadata only behind an advanced/details affordance.

Backend entry points:

- `GET /graph/nodes/{node_id}`
- `GET /graph/nodes/{node_id}/detail`
- `GET /graph/nodes/{node_id}/affective-context`
- `GET /graph/nodes/{node_id}/canonical`
- `GET /graph/targets/{target_id}/changes`
- `GET /graph/contradictions`
- `GET /graph/merges`

### Relationship Detail Requirements

Selecting an edge should show:

- relationship type;
- source node;
- target node;
- direction;
- description;
- lifecycle state;
- confidence or trust fields when present;
- emotional summary when present;
- temporal summary when present;
- supporting sources when available.

For relationship contexts, the UI should support state history:

- current status or closeness;
- previous relationship states;
- valid time range;
- source/evidence references;
- emotional summaries or original user wording when available.

Backend entry points:

- `GET /graph/nodes/{node_id}/relationships`
- `GET /graph/relationship-contexts/{context_id}/detail`
- `GET /graph/relationship-contexts/{context_id}/states`

### Evidence Drawer

The evidence drawer is a reusable component opened from chat, entity detail,
relationship detail, timeline items, and map items.

It should show:

- source type;
- channel;
- source-created time;
- received time;
- source summary or text/transcript reference when available;
- linked node or claim references;
- extraction or provenance metadata when available;
- confidence/trust labels;
- privacy labels;
- source ids without making UUIDs visually dominant.

Backend entry point:

- `GET /graph/targets/{target_id}/evidence`

### Timeline View

Timeline should be a first-class navigation mode inside Memory Graph.

It should support:

- viewing memories connected to a selected node;
- filtering by date range;
- showing time basis, such as event time, source time, ingestion time, or valid
  time when available;
- showing time precision;
- opening item detail and evidence;
- preserving affective summaries and original user wording when present.

Backend entry point:

- `GET /graph/nodes/{node_id}/timeline`

### Map View

Map should be a first-class navigation mode for place-linked memories.

It should support:

- seed-based map exploration;
- city and country filters;
- date range filters;
- place markers;
- event markers or place-linked event lists;
- selecting a marker to open related graph detail;
- timeline side list for map results;
- handling places without exact coordinates.

Backend entry point:

- `GET /graph/views/map`

### Correction And Maintenance Actions

The first graph UI can be read-heavy, but it must leave space for correction
workflows.

Near-term actions:

- ask chat about selected node;
- propose correction through chat;
- open evidence;
- mark something stale, disputed, confirmed, or wrong when supported by the
  backend;
- inspect contradictions;
- inspect merge history.

Later actions:

- merge duplicate entities;
- split incorrectly merged entities;
- apply or revert proposed merges;
- edit lifecycle state;
- edit contact/external-reference data;
- inspect and correct profile memories.

Mutation actions should be explicit, auditable, and confirmation-based.

## View 3: Graph Analytics

### Purpose

The Graph Analytics workspace gives the owner a compact overview of graph size,
coverage, health, and memory patterns.

This is not a business intelligence dashboard. It is a personal graph health and
exploration dashboard.

### Required Widgets

The MVP analytics view should include:

- node counts by label;
- relationship counts by type;
- top connected nodes;
- top emotion tags;
- unresolved contradiction count;
- include archived toggle;
- result limit control.

Backend entry point:

- `GET /graph/analytics/summary`

### Recommended Future Widgets

These may require additional backend support:

- source count by channel;
- recent ingestion activity;
- memories by month;
- confidence distribution;
- trust level distribution;
- privacy level distribution;
- lifecycle state distribution;
- stale facts count;
- disputed facts count;
- unconfirmed contact details;
- merge proposals awaiting review;
- graph density by node label;
- places with most memories;
- topics with most recent activity.

### Analytics Interactions

Analytics widgets should not be static charts only. They should create
navigation paths:

- clicking a node label opens filtered search;
- clicking a relationship type filters graph relationships;
- clicking a top connected node opens its graph neighborhood;
- clicking unresolved contradictions opens contradiction review;
- clicking an emotion tag opens related memories when supported.

## Cross-View Requirements

### Provenance And Trust

The UI must make provenance and trust visible without making every screen feel
like an audit log.

Use compact badges, drawers, and details sections for:

- user-confirmed;
- source-stated;
- LLM-inferred;
- system-derived;
- externally enriched;
- contradicted;
- stale;
- unknown or low confidence.

Answers and graph detail should not present inferred or contradicted data as
equally certain as confirmed data.

### Privacy

Privacy labels should be visible on memory-bearing nodes, sources, claims,
relationships, profile memories, and sensitive metadata when available.

Suggested privacy states:

- normal;
- private;
- sensitive;
- local only;
- hidden.

Sensitive values such as contact details, addresses, profile memories, and
relationship details should be visually identifiable and should not be exposed
through noisy previews when the user is not actively inspecting them.

### Affective Memory

The UI must support affective memory as a first-class concept.

Where available, detail views should show:

- emotional summary;
- emotional valence;
- emotional intensity;
- emotion tags;
- original user wording;
- whether the perception is user-stated or inferred;
- relationship context over time.

This should be presented as subjective memory context, not objective truth about
the target.

### Empty, Loading, And Error States

Every major surface must define states for:

- no graph data yet;
- no search results;
- no selected node;
- graph too dense;
- backend unavailable;
- authentication failure;
- request failed;
- pending process waiting for user input;
- cancelled process;
- stale or archived data hidden by filters;
- partial data where evidence or coordinates are missing.

### Authentication

The MVP web frontend uses static bearer-token authentication for chat endpoints.
The UI should support entering or configuring the token for local/private use,
but it should not design a full public account system for the MVP.

### Accessibility And Responsiveness

The frontend should provide:

- keyboard-accessible navigation and controls;
- accessible labels for icon buttons;
- sufficient color contrast;
- graph alternatives through lists or tables;
- responsive behavior for mobile, tablet, and desktop;
- layouts that avoid overlapping labels, controls, graph nodes, and drawers.

## Frontend Routes

Suggested route structure:

- `/chat`
- `/graph`
- `/graph/node/:nodeId`
- `/graph/node/:nodeId/timeline`
- `/graph/map`
- `/analytics`

Route names can change, but the frontend should support direct links to graph
nodes and major graph views.

## MVP Scope

The first usable frontend should deliver:

- chat workspace using the real chat API;
- graph search;
- focused neighborhood graph rendering;
- selected node detail inspector;
- source/evidence drawer;
- timeline tab for selected node;
- map tab or map route for place-linked memories;
- analytics summary dashboard;
- cross-links from chat evidence to graph detail;
- basic privacy/trust/status badges;
- loading, empty, and error states.

## Out Of Scope For MVP

The MVP frontend should not include:

- public marketing or onboarding pages;
- multi-tenant user administration;
- billing or plan limits;
- arbitrary raw database administration;
- rendering the entire graph by default;
- full manual graph editing;
- full merge/split/revert workflows;
- complex media galleries beyond evidence references;
- complete structured query builder unless explicitly prioritized later.

## Design Assistant Deliverables

Design assistants should produce:

- information architecture for the three main workspaces;
- desktop and mobile wireframes;
- high-fidelity designs for Chat, Memory Graph, Entity Detail, Evidence Drawer,
  Timeline, Map, and Analytics;
- component inventory and states;
- visual encoding system for node types, relationship types, trust, privacy,
  lifecycle, and contradiction status;
- interaction flows for storing a memory, answering clarification, asking a
  question, opening evidence, navigating graph context, and reviewing a
  contradiction;
- empty, loading, error, and dense-graph states;
- implementation notes tied to backend API contracts.

## Initial Success Criteria

The frontend is successful when:

- the user can use web chat as a substitute for Telegram;
- the user can search for a graph entity;
- the user can open a focused graph neighborhood;
- the user can inspect an entity with relationships, evidence, trust, privacy,
  and changes;
- the user can open timeline and map views from graph context;
- the user can see graph analytics at a glance;
- the user can move from chat answer evidence into graph inspection;
- the UI helps identify uncertainty and provenance without overwhelming the
  user.
