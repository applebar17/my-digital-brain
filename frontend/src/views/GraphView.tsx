import { FormEvent, useState } from "react";
import {
  getEntityDetail,
  getMapView,
  getNeighborhoodView,
  getTimelineForNode,
  searchNodes
} from "../api/graph";
import { Badge } from "../components/Badge";
import { EmptyState } from "../components/EmptyState";
import { Panel } from "../components/Panel";
import { StatusLine } from "../components/StatusLine";
import { compactId, formatUnknown, nodeId, nodeTitle } from "../lib/graphLabels";
import type {
  EntityDetailResult,
  GraphViewNode,
  GraphViewResult,
  MapViewResult,
  NodeSearchResult,
  TimelineResult
} from "../types/graph";

const nodeLabels = [
  "",
  "Person",
  "Event",
  "Place",
  "Organization",
  "Object",
  "Animal",
  "SocialCircle",
  "Topic",
  "Source",
  "Claim",
  "Perception",
  "RelationshipContext",
  "ProfileMemory"
];

export function GraphView() {
  const [query, setQuery] = useState("");
  const [label, setLabel] = useState("");
  const [depth, setDepth] = useState(1);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [results, setResults] = useState<NodeSearchResult[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string>();
  const [detail, setDetail] = useState<EntityDetailResult>();
  const [graph, setGraph] = useState<GraphViewResult>();
  const [timeline, setTimeline] = useState<TimelineResult>();
  const [mapView, setMapView] = useState<MapViewResult>();
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>();
  const [errorMessage, setErrorMessage] = useState<string>();

  async function handleSearch(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setIsLoading(true);
    setErrorMessage(undefined);
    setStatusMessage("Searching graph...");
    try {
      const found = await searchNodes({
        query: query.trim() || undefined,
        label: label || undefined,
        limit: 25
      });
      setResults(found);
      setStatusMessage(`${found.length} result${found.length === 1 ? "" : "s"} found`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to search graph.");
      setStatusMessage(undefined);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSelectNode(id: string) {
    if (!id) {
      return;
    }
    setSelectedNodeId(id);
    setIsLoading(true);
    setErrorMessage(undefined);
    setStatusMessage("Loading graph context...");
    try {
      const [nextDetail, nextGraph, nextTimeline, nextMapView] = await Promise.all([
        getEntityDetail(id, true, includeArchived, 50),
        getNeighborhoodView(id, depth, true, includeArchived, 100),
        getTimelineForNode(id, undefined, undefined, true, 100),
        getMapView(id, undefined, undefined, undefined, undefined, 100)
      ]);
      setDetail(nextDetail);
      setGraph(nextGraph);
      setTimeline(nextTimeline);
      setMapView(nextMapView);
      setStatusMessage("Graph context loaded");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load graph context.");
      setStatusMessage(undefined);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="workspace graph-workspace">
      <div className="workspace-header">
        <div>
          <p className="eyebrow">Focused Neighborhoods</p>
          <h2>Memory Graph</h2>
        </div>
        <div className="toolbar">
          <label className="inline-toggle">
            <input
              checked={includeArchived}
              onChange={(event) => setIncludeArchived(event.target.checked)}
              type="checkbox"
            />
            Include archived
          </label>
          <label className="depth-control">
            Depth
            <input
              value={depth}
              onChange={(event) => setDepth(Number(event.target.value))}
              type="number"
              min="1"
              max="3"
            />
          </label>
        </div>
      </div>

      <div className="graph-layout">
        <Panel title="Search" eyebrow="Seed Node">
          <form className="search-form" onSubmit={handleSearch}>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search people, places, events, topics..."
            />
            <select value={label} onChange={(event) => setLabel(event.target.value)}>
              {nodeLabels.map((item) => (
                <option key={item || "all"} value={item}>
                  {item || "All labels"}
                </option>
              ))}
            </select>
            <button className="button-primary" type="submit" disabled={isLoading}>
              Search
            </button>
          </form>
          <StatusLine status={errorMessage ? "error" : "success"} message={errorMessage ?? statusMessage} />
          <div className="result-list">
            {results.length === 0 ? (
              <EmptyState title="No selected seed" body="Search for a node to start graph inspection." />
            ) : (
              results.map((node) => {
                const id = nodeId(node);
                return (
                  <button
                    className={`result-item ${selectedNodeId === id ? "is-active" : ""}`}
                    key={id || nodeTitle(node)}
                    type="button"
                    onClick={() => handleSelectNode(id)}
                  >
                    <span>{nodeTitle(node)}</span>
                    <small>
                      {node.label} {id ? compactId(id) : ""}
                    </small>
                  </button>
                );
              })
            )}
          </div>
        </Panel>

        <Panel title="Neighborhood" eyebrow="Graph View">
          {graph ? (
            <GraphCanvas graph={graph} selectedNodeId={selectedNodeId} onSelectNode={handleSelectNode} />
          ) : (
            <EmptyState
              title="No graph rendered"
              body="Select a seed node to load a focused graph neighborhood."
            />
          )}
        </Panel>

        <aside className="side-stack">
          <EntityInspector detail={detail} />
          <TimelinePanel timeline={timeline} />
          <MapPanel mapView={mapView} />
        </aside>
      </div>
    </div>
  );
}

function GraphCanvas({
  graph,
  selectedNodeId,
  onSelectNode
}: {
  graph: GraphViewResult;
  selectedNodeId?: string;
  onSelectNode: (nodeId: string) => void;
}) {
  const width = 720;
  const height = 480;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) / 2 - 84;
  const positions = new Map<string, { x: number; y: number }>();

  graph.nodes.forEach((node, index) => {
    if (node.id === graph.seed_id) {
      positions.set(node.id, { x: centerX, y: centerY });
      return;
    }
    const angle = ((index || 1) / Math.max(graph.nodes.length - 1, 1)) * Math.PI * 2;
    positions.set(node.id, {
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius
    });
  });

  return (
    <div className="graph-canvas-wrap">
      <svg className="graph-canvas" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Graph neighborhood">
        {graph.relationships.map((relationship) => {
          const from = positions.get(relationship.from_id);
          const to = positions.get(relationship.to_id);
          if (!from || !to) {
            return null;
          }
          return (
            <g key={relationship.id}>
              <line className="graph-edge" x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
              <text className="graph-edge-label" x={(from.x + to.x) / 2} y={(from.y + to.y) / 2}>
                {relationship.type}
              </text>
            </g>
          );
        })}
        {graph.nodes.map((node) => {
          const position = positions.get(node.id);
          if (!position) {
            return null;
          }
          const selected = selectedNodeId === node.id || graph.seed_id === node.id;
          return (
            <g
              className={`graph-node ${selected ? "is-selected" : ""}`}
              key={node.id}
              role="button"
              tabIndex={0}
              onClick={() => onSelectNode(node.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  onSelectNode(node.id);
                }
              }}
            >
              <rect x={position.x - 54} y={position.y - 24} width="108" height="48" rx="4" />
              <circle className={`node-dot ${privacyClass(node)}`} cx={position.x + 42} cy={position.y - 14} r="4" />
              <text x={position.x} y={position.y - 2}>
                {node.title ?? node.label}
              </text>
              <text className="node-label" x={position.x} y={position.y + 14}>
                {node.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function EntityInspector({ detail }: { detail?: EntityDetailResult }) {
  if (!detail) {
    return (
      <Panel title="Inspector" eyebrow="Selected Node">
        <EmptyState title="Nothing selected" body="Select a node to inspect properties, evidence, and status." />
      </Panel>
    );
  }

  const target = detail.target;
  const properties = Object.entries(target.properties).filter(([key]) => {
    return !["metadata", "id", "embedding"].includes(key);
  });

  return (
    <Panel title={nodeTitle(target)} eyebrow={target.label}>
      <div className="badge-row">
        <Badge>{target.label}</Badge>
        {propertyBadge(target.properties.lifecycle_state, "info")}
        {propertyBadge(target.properties.privacy_level, "privacy")}
        {propertyBadge(target.properties.trust_level, "trust")}
      </div>
      <dl className="property-list">
        {properties.slice(0, 12).map(([key, value]) => (
          <div key={key}>
            <dt>{key}</dt>
            <dd>{formatUnknown(value)}</dd>
          </div>
        ))}
      </dl>
      <div className="metric-grid">
        <Metric label="Relationships" value={detail.relationships.length} />
        <Metric label="Sources" value={detail.sources.length} />
        <Metric label="Changes" value={detail.changes.length} />
        <Metric label="Contradictions" value={detail.contradictions.length} tone="danger" />
      </div>
    </Panel>
  );
}

function TimelinePanel({ timeline }: { timeline?: TimelineResult }) {
  return (
    <Panel title="Timeline" eyebrow="Selected Node">
      {!timeline || timeline.items.length === 0 ? (
        <EmptyState title="No timeline items" body="Time-linked memories will appear after selecting a node." />
      ) : (
        <div className="timeline-list">
          {timeline.items.slice(0, 8).map((item) => (
            <article className="timeline-item" key={item.id}>
              <strong>{item.title ?? item.label}</strong>
              <small>{item.time_value ?? "No time"} {item.time_precision ? `(${item.time_precision})` : ""}</small>
              {item.description && <p>{item.description}</p>}
            </article>
          ))}
        </div>
      )}
    </Panel>
  );
}

function MapPanel({ mapView }: { mapView?: MapViewResult }) {
  return (
    <Panel title="Map Results" eyebrow="Place-Linked Memories">
      {!mapView || (mapView.places.length === 0 && mapView.events.length === 0) ? (
        <EmptyState title="No map context" body="Place-linked memories will appear when coordinates or places exist." />
      ) : (
        <div className="metric-grid">
          <Metric label="Places" value={mapView.places.length} />
          <Metric label="Events" value={mapView.events.length} />
          <Metric label="Timeline" value={mapView.timeline.length} />
          <Metric label="Links" value={mapView.relationships.length} />
        </div>
      )}
    </Panel>
  );
}

function Metric({
  label,
  value,
  tone = "neutral"
}: {
  label: string;
  value: number;
  tone?: "neutral" | "danger";
}) {
  return (
    <div className={`metric metric-${tone}`}>
      <span>{value}</span>
      <small>{label}</small>
    </div>
  );
}

function propertyBadge(value: unknown, tone: "info" | "privacy" | "trust") {
  if (typeof value !== "string" || !value) {
    return null;
  }
  return <Badge tone={tone}>{value}</Badge>;
}

function privacyClass(node: GraphViewNode): string {
  if (node.privacy_level === "sensitive" || node.privacy_level === "private") {
    return "node-dot-privacy";
  }
  if (node.trust_level === "llm_inferred") {
    return "node-dot-warning";
  }
  if (node.trust_level === "contradicted" || node.lifecycle_state === "disputed") {
    return "node-dot-danger";
  }
  return "node-dot-trust";
}
