import type { ChatRuntimeState } from "../types";

interface ChatStatusBarProps {
  runtime: ChatRuntimeState;
}

export function ChatStatusBar({ runtime }: ChatStatusBarProps) {
  const statusText = {
    active: "Ready",
    processing: "Working on your request",
    awaiting_clarification: "Waiting for your answer",
    completed: "Response ready",
    error: "Something needs attention"
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
        <span>{statusText}</span>
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
