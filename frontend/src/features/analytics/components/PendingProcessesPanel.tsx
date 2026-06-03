import type { PendingProcessItem } from "../types";

interface PendingProcessesPanelProps {
  items: PendingProcessItem[];
}

export function PendingProcessesPanel({ items }: PendingProcessesPanelProps) {
  if (items.length === 0) {
    return (
      <div className="memory-pending-processes-empty">
        <strong>No pending processes loaded</strong>
        <p>This panel is reserved for backend pending-process summaries when that surface is available.</p>
      </div>
    );
  }

  return (
    <div className="memory-pending-processes">
      {items.map((item) => (
        <article className="memory-pending-process-row" key={item.id}>
          <div>
            <strong>{item.kind}</strong>
            <span>{item.detail}</span>
          </div>
          <b>{item.status}</b>
        </article>
      ))}
    </div>
  );
}
