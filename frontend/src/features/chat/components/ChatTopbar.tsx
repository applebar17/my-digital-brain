import { ChatIcon } from "./ChatIcon";

interface ChatTopbarProps {
  activeConversationId: string;
  isHistoryOpen: boolean;
  onToggleHistory: () => void;
}

export function ChatTopbar({
  activeConversationId,
  isHistoryOpen,
  onToggleHistory
}: ChatTopbarProps) {
  return (
    <header className="memory-chat-topbar">
      <div className="memory-chat-title-row">
        <button
          className="memory-icon-button"
          type="button"
          title="Open recent chats"
          aria-label="Open recent chats"
          aria-expanded={isHistoryOpen}
          onClick={onToggleHistory}
        >
          <ChatIcon name="panel" />
        </button>
        <div>
          <p className="eyebrow">Conversation Runtime</p>
          <h2>Chat</h2>
        </div>
      </div>
      <div className="memory-chat-meta">
        <span>Web</span>
        <span>{activeConversationId}</span>
      </div>
    </header>
  );
}
