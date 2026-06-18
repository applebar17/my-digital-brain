import { Badge } from "../../../components/Badge";
import { firstString, formatUnknown, nodeId, nodeTitle } from "../../../lib/graphLabels";
import type { NodeSearchResult } from "../../../types/graph";

interface MemoryLogRowProps {
  log: NodeSearchResult;
  isSelected: boolean;
  onSelect: (logId: string) => void;
}

export function MemoryLogRow({ log, isSelected, onSelect }: MemoryLogRowProps) {
  const id = nodeId(log);
  const properties = log.properties;
  const title = firstString(properties.log_text, properties.original_user_words, nodeTitle(log));
  const time = firstString(
    properties.happened_at,
    properties.resolved_start,
    properties.source_time,
    properties.observed_at,
    properties.created_at
  );

  return (
    <button
      className={`memory-log-row ${isSelected ? "is-active" : ""}`}
      type="button"
      onClick={() => onSelect(id)}
    >
      <span>{time === "Untitled" ? "Unknown time" : time}</span>
      <strong>{title}</strong>
      <small>
        {typeof properties.log_kind === "string" && <Badge tone="info">{properties.log_kind}</Badge>}
        {typeof properties.source_kind === "string" && <Badge>{properties.source_kind}</Badge>}
        {hasMedia(log) && <Badge tone="trust">media</Badge>}
      </small>
      {properties.importance ? <em>Importance: {formatUnknown(properties.importance)}</em> : null}
    </button>
  );
}

function hasMedia(log: NodeSearchResult): boolean {
  const mediaRefs = log.properties.media_refs;
  return Array.isArray(mediaRefs) && mediaRefs.length > 0;
}
