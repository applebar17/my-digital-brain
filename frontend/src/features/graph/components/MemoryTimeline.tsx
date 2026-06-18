import { EmptyState } from "../../../components/EmptyState";
import { nodeId } from "../../../lib/graphLabels";
import type { NodeSearchResult } from "../../../types/graph";
import { MemoryLogRow } from "./MemoryLogRow";

interface MemoryTimelineProps {
  logs: NodeSearchResult[];
  selectedLogId?: string;
  isLoading: boolean;
  onSelectLog: (logId: string) => void;
}

export function MemoryTimeline({
  logs,
  selectedLogId,
  isLoading,
  onSelectLog
}: MemoryTimelineProps) {
  if (logs.length === 0) {
    return (
      <EmptyState
        title={isLoading ? "Loading memory logs" : "No memory logs"}
        body={
          isLoading
            ? "Retrieving the selected node's nested memory history."
            : "No MemoryLog records matched the current filters."
        }
      />
    );
  }

  return (
    <div className="memory-log-timeline" aria-busy={isLoading}>
      {logs.map((log) => {
        const id = nodeId(log);
        return (
          <MemoryLogRow
            key={id}
            log={log}
            isSelected={selectedLogId === id}
            onSelect={onSelectLog}
          />
        );
      })}
    </div>
  );
}
