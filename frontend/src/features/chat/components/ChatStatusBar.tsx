import type { ChatRuntimeState } from "../types";

interface ChatStatusBarProps {
  runtime: ChatRuntimeState;
}

export function ChatStatusBar({ runtime }: ChatStatusBarProps) {
  const statusText = {
    active: "Active",
    processing: "Processing",
    awaiting_clarification: "Waiting for clarification",
    completed: "Completed",
    error: "Action needs attention"
  }[runtime.status];
  const syncText =
    runtime.clarificationError?.message ??
    runtime.errorMessage ??
    runtime.statusMessage ??
    (runtime.isSending ? "Syncing context..." : "");

  return (
    <header className="memory-chat-status">
      <div className="memory-chat-status-primary">
        <span className={`memory-status-dot ${runtime.status === "error" ? "is-error" : ""}`} />
        <span>Conversation Status: {statusText}</span>
      </div>
      {syncText && (
        <div className={`memory-chat-status-secondary ${runtime.status === "error" ? "is-error" : ""}`}>
          {runtime.isSending && <span className="memory-spinner" aria-hidden="true" />}
          <span>{syncText}</span>
        </div>
      )}
    </header>
  );
}
