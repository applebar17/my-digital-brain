# Analytics and Shared UI Requirements

## Graph analytics

Graph Analytics gives the owner a compact view of graph size, coverage, and
health. It is a personal exploration surface, not a business-intelligence
dashboard.

The initial view includes:

- node counts by type and relationship counts by type;
- the most connected nodes;
- prominent emotion tags;
- unresolved contradiction count; and
- a way to include archived information and limit displayed results.

Analytics are navigable: selecting a node or category opens the relevant graph
view; selecting an unresolved contradiction opens its available review context;
selecting an emotion opens related memories when supported.

Additional metrics are not requirements until separately prioritized.

## Shared presentation requirements

### Evidence and trust

The UI makes evidence and trust inspectable without making every screen feel
like an audit log. Where available, it distinguishes user-confirmed,
source-stated, inferred, system-derived, externally enriched, contradicted,
stale, or low-confidence information. Answers and details must not present
uncertain information as equally certain as confirmed information.

### Privacy

Available privacy classifications are visible when relevant. Sensitive values
such as contact details, addresses, profile memories, or relationship details
are not exposed in noisy previews when the owner is not actively inspecting
them. Privacy semantics are owned by [privacy and trust
requirements](../privacy-and-trust.md).

### Affective context

Where available, detail views can show an emotional summary, valence or
intensity, emotion tags, original user wording, whether a perception was
user-stated or inferred, and relationship context over time. These are
presented as subjective memory context, not objective truth about the target.
The domain meaning is owned by [affective memory](../../network/affective-memory.md).

### Empty, loading, and failure states

Major surfaces provide understandable states for empty data, no search result,
no selection, dense graph results, unavailable services, failed requests,
missing evidence or coordinates, and data hidden by a filter. A clarification
waiting for an answer is an interaction state, not an indefinite loading
indicator; chat-specific behavior is defined in [Chat Workspace
Requirements](chat-workspace.md).

### Accessibility and responsiveness

- Navigation and controls are keyboard accessible and have accessible labels.
- Text and visual states maintain sufficient contrast.
- Graph information has a list or table alternative.
- Layouts support mobile, tablet, and desktop without overlapping graph labels,
  controls, or detail panels.
- Important distinctions are not communicated by color alone.

## Acceptance checks

- Analytics communicate the initial graph-health measures and offer useful
  navigation into the graph.
- Evidence, uncertainty, privacy, and subjective context are understandable
  wherever relevant data is shown.
- Empty, unavailable, and filtered-out data are distinguishable to the owner.
- Core navigation and graph inspection remain accessible across screen sizes.
