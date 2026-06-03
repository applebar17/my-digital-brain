import { useEffect, useState } from "react";
import { getAnalyticsSummary } from "../api/graph";
import { Badge } from "../components/Badge";
import { EmptyState } from "../components/EmptyState";
import { Panel } from "../components/Panel";
import { StatusLine } from "../components/StatusLine";
import type { GraphAnalyticsItem, GraphAnalyticsSummary } from "../types/graph";

export function AnalyticsView() {
  const [includeArchived, setIncludeArchived] = useState(false);
  const [limit, setLimit] = useState(20);
  const [summary, setSummary] = useState<GraphAnalyticsSummary>();
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>();
  const [statusMessage, setStatusMessage] = useState<string>();

  useEffect(() => {
    void loadSummary();
  }, []);

  async function loadSummary() {
    setIsLoading(true);
    setErrorMessage(undefined);
    setStatusMessage("Loading analytics...");
    try {
      const nextSummary = await getAnalyticsSummary(includeArchived, limit);
      setSummary(nextSummary);
      setStatusMessage("Analytics loaded");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load analytics.");
      setStatusMessage(undefined);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="workspace analytics-workspace">
      <div className="workspace-header">
        <div>
          <p className="eyebrow">Graph Health</p>
          <h2>Analytics</h2>
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
            Limit
            <input
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
              type="number"
              min="1"
              max="200"
            />
          </label>
          <button className="button-primary" type="button" onClick={loadSummary} disabled={isLoading}>
            Refresh
          </button>
        </div>
      </div>

      <StatusLine status={errorMessage ? "error" : "success"} message={errorMessage ?? statusMessage} />

      {!summary ? (
        <EmptyState title="No analytics loaded" body="Refresh to load the graph analytics summary." />
      ) : (
        <div className="analytics-grid">
          <Panel title="Graph Totals" eyebrow="Coverage">
            <div className="metric-grid">
              <Metric label="Node types" value={Object.keys(summary.node_counts).length} />
              <Metric label="Relationship types" value={Object.keys(summary.relationship_counts).length} />
              <Metric
                label="Contradictions"
                value={summary.unresolved_contradictions}
                tone={summary.unresolved_contradictions > 0 ? "danger" : "neutral"}
              />
            </div>
          </Panel>

          <DistributionPanel title="Nodes By Label" items={summary.node_counts} />
          <DistributionPanel title="Relationships By Type" items={summary.relationship_counts} />
          <RankedPanel title="Top Connected Nodes" items={summary.top_connected_nodes} />
          <RankedPanel title="Top Emotion Tags" items={summary.top_emotion_tags} />
        </div>
      )}
    </div>
  );
}

function DistributionPanel({ title, items }: { title: string; items: Record<string, number> }) {
  const entries = Object.entries(items).sort(([, a], [, b]) => b - a);
  return (
    <Panel title={title} eyebrow="Distribution">
      {entries.length === 0 ? (
        <EmptyState title="No data" body="This distribution is empty for the current filters." />
      ) : (
        <div className="distribution-list">
          {entries.map(([key, count]) => (
            <div className="distribution-row" key={key}>
              <span>{key}</span>
              <Badge tone="info">{count}</Badge>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function RankedPanel({ title, items }: { title: string; items: GraphAnalyticsItem[] }) {
  return (
    <Panel title={title} eyebrow="Ranked">
      {items.length === 0 ? (
        <EmptyState title="No ranked items" body="Ranked results will appear when the backend has enough graph data." />
      ) : (
        <div className="distribution-list">
          {items.map((item) => (
            <div className="distribution-row" key={item.key}>
              <span>{item.label ?? item.key}</span>
              <Badge tone="info">{item.count}</Badge>
            </div>
          ))}
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
