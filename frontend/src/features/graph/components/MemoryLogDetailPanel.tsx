import { Badge } from "../../../components/Badge";
import { EmptyState } from "../../../components/EmptyState";
import { formatUnknown, nodeId, nodeTitle } from "../../../lib/graphLabels";
import type { MemoryLogDetailResult, NodeSearchResult } from "../../../types/graph";

interface MemoryLogDetailPanelProps {
  detail?: MemoryLogDetailResult;
  selectedLogId?: string;
  isLoading: boolean;
}

export function MemoryLogDetailPanel({
  detail,
  selectedLogId,
  isLoading
}: MemoryLogDetailPanelProps) {
  if (!selectedLogId) {
    return (
      <EmptyState
        title="No log selected"
        body="Select a MemoryLog from the timeline to inspect hosts, context, and media references."
      />
    );
  }
  if (!detail) {
    return (
      <EmptyState
        title={isLoading ? "Loading log detail" : "Log detail unavailable"}
        body={
          isLoading
            ? "Retrieving hosts, involved nodes, relationship context, and media references."
            : "The selected MemoryLog detail could not be loaded."
        }
      />
    );
  }

  const log = detail.memory_log;
  return (
    <article className="memory-log-detail">
      <header>
        <div>
          <p className="eyebrow">MemoryLog</p>
          <h4>{formatUnknown(log.properties.log_text ?? log.properties.original_user_words)}</h4>
        </div>
        <div className="badge-row">
          {badge(log.properties.log_kind, "info")}
          {badge(log.properties.source_kind, "neutral")}
          {badge(log.properties.importance, "trust")}
        </div>
      </header>

      <dl className="memory-property-list">
        {detailField("Time", firstDefined(log, "happened_at", "resolved_start", "source_time", "observed_at", "created_at"))}
        {detailField("Original wording", log.properties.original_user_words)}
        {detailField("Confidence", log.properties.confidence)}
        {detailField("Source refs", log.properties.source_ids)}
        {detailField("Media refs", log.properties.media_refs)}
      </dl>

      <NodeBucket title="Hosts" nodes={detail.hosts} />
      <NodeBucket title="Involved" nodes={detail.involved} />
      <NodeBucket title="Relationship Context" nodes={detail.relationship_contexts} />
      <NodeBucket title="Media Refs" nodes={detail.media_assets} />

      <section className="memory-log-relationship-list">
        <h5>Relationships</h5>
        {detail.relationships.length === 0 ? (
          <p className="memory-muted">No relationships returned for this MemoryLog.</p>
        ) : (
          detail.relationships.map((relationship) => (
            <div key={String(relationship.properties.id ?? `${relationship.from_id}:${relationship.to_id}`)}>
              <strong>{relationship.type}</strong>
              <span>{compactPair(relationship.from_id, relationship.to_id)}</span>
            </div>
          ))
        )}
      </section>
    </article>
  );
}

function NodeBucket({ title, nodes }: { title: string; nodes: NodeSearchResult[] }) {
  return (
    <section className="memory-log-node-bucket">
      <h5>{title}</h5>
      {nodes.length === 0 ? (
        <p className="memory-muted">None returned.</p>
      ) : (
        nodes.map((node) => (
          <div key={nodeId(node) || nodeTitle(node)}>
            <strong>{nodeTitle(node)}</strong>
            <span>{node.label}</span>
          </div>
        ))
      )}
    </section>
  );
}

function detailField(label: string, value: unknown) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  return (
    <div>
      <dt>{label}</dt>
      <dd>{formatUnknown(value)}</dd>
    </div>
  );
}

function badge(value: unknown, tone: "neutral" | "trust" | "info") {
  return typeof value === "string" && value ? <Badge tone={tone}>{value}</Badge> : null;
}

function firstDefined(node: NodeSearchResult, ...keys: string[]): unknown {
  for (const key of keys) {
    const value = node.properties[key];
    if (value !== null && value !== undefined && value !== "") {
      return value;
    }
  }
  return undefined;
}

function compactPair(fromId: string, toId: string): string {
  return `${fromId.slice(0, 8)} -> ${toId.slice(0, 8)}`;
}
