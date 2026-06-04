import { Badge } from "../../../components/Badge";
import { EmptyState } from "../../../components/EmptyState";
import { formatUnknown, nodeTitle } from "../../../lib/graphLabels";
import type { EntityDetailResult } from "../../../types/graph";

interface GraphInspectorPanelProps {
  detail?: EntityDetailResult;
  selectedNodeId?: string;
}

export function GraphInspectorPanel({ detail, selectedNodeId }: GraphInspectorPanelProps) {
  if (!detail) {
    return (
      <aside className="memory-window memory-inspector-window">
        <header className="memory-window-header">
          <div>
            <p className="eyebrow">Inspector</p>
            <h3>Selected Node</h3>
          </div>
        </header>
        <EmptyState
          title={selectedNodeId ? "Loading selection" : "Nothing selected"}
          body={
            selectedNodeId
              ? "Loading evidence and graph state for the selected node."
              : "Select a node to inspect its evidence and graph state."
          }
        />
      </aside>
    );
  }

  const target = detail.target;
  const properties = Object.entries(target.properties).filter(([key]) => {
    return !["metadata", "id", "embedding"].includes(key);
  });

  return (
    <aside className="memory-window memory-inspector-window">
      <header className="memory-window-header">
        <div>
          <p className="eyebrow">{target.label}</p>
          <h3>{nodeTitle(target)}</h3>
        </div>
      </header>

      <div className="memory-inspector-body">
        <div className="badge-row">
          <Badge tone="info">{target.label}</Badge>
          {propertyBadge(target.properties.lifecycle_state, "neutral")}
          {propertyBadge(target.properties.privacy_level, "privacy")}
          {propertyBadge(target.properties.trust_level, "trust")}
        </div>

        {descriptionOf(target.properties) && (
          <p className="memory-node-description">{descriptionOf(target.properties)}</p>
        )}

        <div className="memory-inspector-metrics">
          <Metric label="Relationships" value={detail.relationships.length} />
          <Metric label="Sources" value={detail.sources.length} />
          <Metric label="Changes" value={detail.changes.length} />
          <Metric label="Conflicts" value={detail.contradictions.length} danger={detail.contradictions.length > 0} />
        </div>

        {affectiveText(target.properties) && (
          <section className="memory-affective-block">
            <h4>Affective Context</h4>
            <p>{affectiveText(target.properties)}</p>
          </section>
        )}

        <section className="memory-property-section">
          <h4>Properties</h4>
          <dl className="memory-property-list">
            {properties.slice(0, 12).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{formatUnknown(value)}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="memory-property-section">
          <h4>Direct Evidence</h4>
          {detail.sources.length === 0 ? (
            <p className="memory-muted">No source evidence returned for this node.</p>
          ) : (
            <div className="memory-evidence-list">
              {detail.sources.slice(0, 4).map((source) => (
                <article className="memory-evidence-row" key={String(source.properties.id ?? nodeTitle(source))}>
                  <strong>{nodeTitle(source)}</strong>
                  <span>{source.label}</span>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </aside>
  );
}

function Metric({ label, value, danger = false }: { label: string; value: number; danger?: boolean }) {
  return (
    <div className={`memory-mini-metric ${danger ? "is-danger" : ""}`}>
      <span>{value}</span>
      <small>{label}</small>
    </div>
  );
}

function propertyBadge(value: unknown, tone: "neutral" | "privacy" | "trust") {
  if (typeof value !== "string" || !value) {
    return null;
  }
  return <Badge tone={tone}>{value}</Badge>;
}

function descriptionOf(properties: Record<string, unknown>): string | undefined {
  const value = properties.description ?? properties.text;
  return typeof value === "string" ? value : undefined;
}

function affectiveText(properties: Record<string, unknown>): string | undefined {
  const value = properties.emotional_summary ?? properties.original_user_words;
  return typeof value === "string" ? value : undefined;
}
