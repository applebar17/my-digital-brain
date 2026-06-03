import type { PendingProcessRef } from "../../../types/chat";

interface PendingProcessNoticeProps {
  pendingProcess?: PendingProcessRef | null;
}

export function PendingProcessNotice({ pendingProcess }: PendingProcessNoticeProps) {
  if (!pendingProcess) {
    return null;
  }

  return (
    <div className="memory-pending-notice">
      <span className="memory-spinner" aria-hidden="true" />
      <div>
        <strong>{pendingProcess.kind}</strong>
        <p>{pendingProcess.question ?? "The backend is waiting for follow-up context."}</p>
      </div>
    </div>
  );
}
