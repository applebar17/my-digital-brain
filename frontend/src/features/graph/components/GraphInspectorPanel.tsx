import { Badge } from "../../../components/Badge";
import { EmptyState } from "../../../components/EmptyState";
import type { MemoryLogFilters as MemoryLogFilterValues } from "../../../api/graph";
import { formatUnknown, nodeTitle } from "../../../lib/graphLabels";
import type {
  EntityDetailResult,
  MemoryLogDetailResult,
  NodeSearchResult,
  SemanticMemoryHit,
  SemanticMemorySearchResult
} from "../../../types/graph";
import { MemoryLogDetailPanel } from "./MemoryLogDetailPanel";
import { MemoryLogFilters } from "./MemoryLogFilters";
import { MemoryTimeline } from "./MemoryTimeline";
import { RetrievalDiagnosticsPanel } from "./RetrievalDiagnosticsPanel";
import { RetrievalEvidencePanel } from "./RetrievalEvidencePanel";

interface GraphInspectorPanelProps {
  detail?: EntityDetailResult;
  selectedNodeId?: string;
  selectedHit?: SemanticMemoryHit;
  retrievalResult?: SemanticMemorySearchResult;
  memoryLogs: NodeSearchResult[];
  memoryLogFilters: MemoryLogFilterValues;
  selectedMemoryLogId?: string;
  selectedMemoryLogDetail?: MemoryLogDetailResult;
  isMemoryLogLoading: boolean;
  onClose: () => void;
  onFocusNeighborhood: () => void;
  onMemoryLogFiltersChange: (filters: MemoryLogFilterValues) => void;
  onResetMemoryLogFilters: () => void;
  onSelectMemoryLog: (logId: string) => void;
}

export function GraphInspectorPanel({
  detail,
  selectedNodeId,
  selectedHit,
  retrievalResult,
  memoryLogs,
  memoryLogFilters,
  selectedMemoryLogId,
  selectedMemoryLogDetail,
  isMemoryLogLoading,
  onClose,
  onFocusNeighborhood,
  onMemoryLogFiltersChange,
  onResetMemoryLogFilters,
  onSelectMemoryLog
}: GraphInspectorPanelProps) {
  const isOpen = Boolean(selectedNodeId);
  const className = `memory-window memory-inspector-window ${isOpen ? "is-open" : "is-closed"}`;

  if (!detail) {
    return (
      <aside className={className} aria-hidden={!isOpen}>
        <header className="memory-window-header">
          <div>
            <p className="eyebrow">Inspector</p>
            <h3>Selected Node</h3>
          </div>
          {selectedNodeId ? (
            <button
              className="memory-window-close"
              type="button"
              aria-label="Close selected node details"
              title="Close selected node details"
              onClick={onClose}
            >
              X
            </button>
          ) : null}
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
  const propertyEntries = Object.entries(target.properties);
  const visibleProperties = propertyEntries.filter(([key]) => !isTechnicalProperty(key));
  const metadataProperties = propertyEntries.filter(([key]) => isTechnicalProperty(key));

  return (
    <aside className={className} aria-hidden={!isOpen}>
      <header className="memory-window-header">
        <div>
          <p className="eyebrow">{target.label}</p>
          <h3>{nodeTitle(target)}</h3>
        </div>
        <div className="memory-window-actions">
          <button type="button" onClick={onFocusNeighborhood}>
            Focus
          </button>
          <button
            className="memory-window-close"
            type="button"
            aria-label="Close selected node details"
            title="Close selected node details"
            onClick={onClose}
          >
            X
          </button>
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
          {visibleProperties.length === 0 ? (
            <p className="memory-muted">No display properties returned for this node.</p>
          ) : (
            <dl className="memory-property-list">
              {visibleProperties.slice(0, 12).map(([key, value]) => (
                <div key={key}>
                  <dt>{formatPropertyLabel(key)}</dt>
                  <dd>{formatUnknown(value)}</dd>
                </div>
              ))}
            </dl>
          )}
        </section>

        <details className="memory-metadata-section">
          <summary>
            <span>Technical Metadata</span>
            <small>{metadataProperties.length} fields</small>
          </summary>
          {metadataProperties.length === 0 ? (
            <p className="memory-muted">No hidden metadata returned for this node.</p>
          ) : (
            <dl className="memory-property-list">
              {metadataProperties.map(([key, value]) => (
                <div key={key}>
                  <dt>{formatPropertyLabel(key)}</dt>
                  <dd>{formatUnknown(value)}</dd>
                </div>
              ))}
            </dl>
          )}
        </details>

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

        <section className="memory-property-section memory-log-section">
          <h4>MemoryLog Timeline</h4>
          <MemoryLogFilters
            filters={memoryLogFilters}
            isLoading={isMemoryLogLoading}
            onChange={onMemoryLogFiltersChange}
            onReset={onResetMemoryLogFilters}
          />
          <MemoryTimeline
            logs={memoryLogs}
            selectedLogId={selectedMemoryLogId}
            isLoading={isMemoryLogLoading}
            onSelectLog={onSelectMemoryLog}
          />
        </section>

        <section className="memory-property-section">
          <h4>Selected Log</h4>
          <MemoryLogDetailPanel
            detail={selectedMemoryLogDetail}
            selectedLogId={selectedMemoryLogId}
            isLoading={isMemoryLogLoading}
          />
        </section>

        <section className="memory-property-section">
          <h4>Matched Records</h4>
          <RetrievalEvidencePanel
            hit={selectedHit}
            contextPackages={retrievalResult?.context_packages ?? []}
          />
        </section>

        <details className="memory-metadata-section">
          <summary>
            <span>Retrieval Diagnostics</span>
            <small>{retrievalResult?.trace.length ?? 0} events</small>
          </summary>
          <RetrievalDiagnosticsPanel hit={selectedHit} retrievalResult={retrievalResult} />
        </details>
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

function isTechnicalProperty(key: string): boolean {
  return technicalPropertyKeys.has(key) || key.endsWith("_id") || key.endsWith("_ids");
}

function formatPropertyLabel(key: string): string {
  return key.replaceAll("_", " ");
}

const technicalPropertyKeys = new Set([
  "id",
  "metadata",
  "embedding",
  "created_at",
  "updated_at",
  "source_ids",
  "extraction_run_ids",
  "normalized_name",
  "normalized_value",
  "checksum",
  "content_ref",
  "transcript_ref",
  "external_id",
  "merged_into_id"
]);
