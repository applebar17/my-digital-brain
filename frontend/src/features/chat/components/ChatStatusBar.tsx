import type { ChatRuntimeState } from "../types";

interface ChatStatusBarProps {
  runtime: ChatRuntimeState;
}

export function ChatStatusBar({ runtime }: ChatStatusBarProps) {
  const statusText = runtime.pendingProcess ? "Waiting for clarification" : "Active";
  const syncText = runtime.errorMessage ?? runtime.statusMessage ?? (runtime.isSending ? "Syncing context..." : "");

  return (
    <header className="memory-chat-status">
      <div className="memory-chat-status-primary">
        <span className={`memory-status-dot ${runtime.errorMessage ? "is-error" : ""}`} />
        <span>Conversation Status: {statusText}</span>
      </div>
      {syncText && (
        <div className={`memory-chat-status-secondary ${runtime.errorMessage ? "is-error" : ""}`}>
          {runtime.isSending && <span className="memory-spinner" aria-hidden="true" />}
          <span>{syncText}</span>
        </div>
      )}
    </header>
  );
}
