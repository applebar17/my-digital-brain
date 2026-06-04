import type { ConversationSessionSummary } from "../../../types/chat";
import { filterRecentChats } from "../utils/chatSession";
import { ChatIcon } from "./ChatIcon";

interface ChatHistorySidebarProps {
  recentChats: ConversationSessionSummary[];
  recentSearch: string;
  selectedSessionId?: string;
  openMenuId?: string;
  onSearchChange: (value: string) => void;
  onNewChat: () => void;
  onClose: () => void;
  onSelectChat: (chat: ConversationSessionSummary) => void;
  onToggleMenu: (sessionId: string) => void;
  onDeleteChat: (chat: ConversationSessionSummary) => void;
}

export function ChatHistorySidebar({
  recentChats,
  recentSearch,
  selectedSessionId,
  openMenuId,
  onSearchChange,
  onNewChat,
  onClose,
  onSelectChat,
  onToggleMenu,
  onDeleteChat
}: ChatHistorySidebarProps) {
  const filteredRecentChats = filterRecentChats(recentChats, recentSearch);

  return (
    <aside className="memory-chat-history" aria-label="Recent chats">
      <header className="memory-chat-history-header">
        <strong>Chats</strong>
        <div className="memory-chat-history-header-actions">
          <button
            className="memory-icon-button"
            type="button"
            title="Close recent chats"
            aria-label="Close recent chats"
            onClick={onClose}
          >
            <ChatIcon name="panel" />
          </button>
        </div>
      </header>
      <button className="memory-chat-history-action" type="button" onClick={onNewChat}>
        <ChatIcon name="new" />
        <span>New chat</span>
      </button>
      <div className="memory-chat-history-search">
        <ChatIcon name="search" />
        <input
          type="search"
          value={recentSearch}
          placeholder="Search chat"
          aria-label="Search recent chats"
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </div>
      <div className="memory-chat-recents">
        <p>Recent</p>
        {filteredRecentChats.length === 0 ? (
          <span className="memory-chat-history-empty">
            {recentChats.length === 0 ? "No recent chats yet" : "No matching chats"}
          </span>
        ) : (
          filteredRecentChats.map((chat) => (
            <RecentChatRow
              key={chat.session_id}
              chat={chat}
              isActive={chat.session_id === selectedSessionId}
              isMenuOpen={openMenuId === chat.session_id}
              onSelect={() => onSelectChat(chat)}
              onToggleMenu={() => onToggleMenu(chat.session_id)}
              onDelete={() => onDeleteChat(chat)}
            />
          ))
        )}
      </div>
    </aside>
  );
}

interface RecentChatRowProps {
  chat: ConversationSessionSummary;
  isActive: boolean;
  isMenuOpen: boolean;
  onSelect: () => void;
  onToggleMenu: () => void;
  onDelete: () => void;
}

function RecentChatRow({
  chat,
  isActive,
  isMenuOpen,
  onSelect,
  onToggleMenu,
  onDelete
}: RecentChatRowProps) {
  return (
    <div className={`memory-chat-recent ${isActive ? "is-active" : ""}`}>
      <button className="memory-chat-recent-main" type="button" onClick={onSelect}>
        <span>{chat.title}</span>
        {chat.last_message_preview ? <small>{chat.last_message_preview}</small> : null}
      </button>
      <div className="memory-chat-recent-menu">
        <button
          className="memory-chat-recent-menu-trigger"
          type="button"
          title="Chat actions"
          aria-label={`Actions for ${chat.title}`}
          aria-expanded={isMenuOpen}
          onClick={onToggleMenu}
        >
          <ChatIcon name="more" />
        </button>
        {isMenuOpen ? (
          <div className="memory-chat-recent-menu-popover" role="menu">
            <button className="is-danger" type="button" role="menuitem" onClick={onDelete}>
              <ChatIcon name="trash" />
              <span>Delete chat</span>
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
