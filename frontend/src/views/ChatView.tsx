import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { getChatSession, postChatMessage } from "../api/chat";
import {
  defaultConversationId,
  defaultOwnerId,
  defaultSenderId,
  defaultWebChatToken
} from "../config";
import { ChatComposer } from "../features/chat/components/ChatComposer";
import { ChatMessageList } from "../features/chat/components/ChatMessageList";
import { ChatStatusBar } from "../features/chat/components/ChatStatusBar";
import type { ChatRuntimeState, RenderedChatMessage } from "../features/chat/types";
import type {
  ConversationMessage,
  ConversationSessionDetail,
  PendingProcessRef
} from "../types/chat";

const tokenStorageKey = "my-digital-brain.web-chat-token";
const recentChatStorageKey = "my-digital-brain.web-chat-recents";

interface RecentChatSummary {
  conversationId: string;
  sessionId?: string;
  title: string;
  lastMessage?: string;
  updatedAt: string;
}

export function ChatView() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<RenderedChatMessage[]>([]);
  const [pendingProcess, setPendingProcess] = useState<PendingProcessRef | null>(null);
  const [sessionId, setSessionId] = useState<string>();
  const [activeConversationId, setActiveConversationId] = useState(defaultConversationId);
  const [isHistoryOpen, setIsHistoryOpen] = useState(true);
  const [recentChats, setRecentChats] = useState<RecentChatSummary[]>(() => loadRecentChats());
  const [recentSearch, setRecentSearch] = useState("");
  const [processUpdates, setProcessUpdates] = useState<string[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>();
  const [errorMessage, setErrorMessage] = useState<string>();
  const [token] = useState(() => localStorage.getItem(tokenStorageKey) ?? defaultWebChatToken);

  const runtime: ChatRuntimeState = {
    pendingProcess,
    isSending,
    statusMessage,
    errorMessage
  };
  const filteredRecentChats = filterRecentChats(recentChats, recentSearch);

  useEffect(() => {
    if (!isSending || !sessionId) {
      return undefined;
    }

    const activeSessionId = sessionId;
    let isCancelled = false;

    async function pollSession() {
      try {
        const detail = await getChatSession(activeSessionId, token, 20);
        if (isCancelled) {
          return;
        }
        setPendingProcess(detail.pending_process?.process_ref ?? null);
        setProcessUpdates(processUpdatesFromSession(detail));
      } catch {
        if (!isCancelled) {
          setProcessUpdates(["Waiting for backend process updates..."]);
        }
      }
    }

    void pollSession();
    const intervalId = window.setInterval(pollSession, 1600);
    return () => {
      isCancelled = true;
      window.clearInterval(intervalId);
    };
  }, [isSending, sessionId, token]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || isSending) {
      return;
    }

    const messageId = createId();
    const userMessage: RenderedChatMessage = {
      id: messageId,
      role: "user",
      text,
      createdAt: new Date().toISOString()
    };

    setDraft("");
    setMessages((current) => [...current, userMessage]);
    setIsSending(true);
    setErrorMessage(undefined);
    setProcessUpdates(["Message sent", "Waiting for backend processing..."]);
    setStatusMessage("Sending message...");

    try {
      const response = await postChatMessage(
        {
          conversation_id: activeConversationId,
          sender_id: defaultSenderId,
          owner_id: defaultOwnerId,
          message_id: messageId,
          text,
          pending_process_id: pendingProcess?.process_id ?? undefined,
          conversation_history_refs: messages.map((message) => message.id)
        },
        token
      );

      setSessionId(response.session_id);
      setPendingProcess(response.pending_process ?? null);
      setRecentChats((current) =>
        persistRecentChat(
          {
            conversationId: activeConversationId,
            sessionId: response.session_id,
            title: chatTitle([...messages, userMessage]),
            lastMessage: text,
            updatedAt: response.created_at
          },
          current
        )
      );
      setMessages((current) => [
        ...current,
        {
          id: response.response_id,
          role: "assistant",
          text: response.primary_text,
          createdAt: response.created_at,
          status: response.status
        }
      ]);
      setStatusMessage(`Response received: ${response.status}`);
      setProcessUpdates([`Response received: ${response.status}`]);
      window.setTimeout(() => setProcessUpdates([]), 2600);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to send message.");
      setStatusMessage(undefined);
    } finally {
      setIsSending(false);
    }
  }

  async function handleSelectChat(chat: RecentChatSummary) {
    if (isSending) {
      return;
    }
    setActiveConversationId(chat.conversationId);
    setSessionId(chat.sessionId);
    setErrorMessage(undefined);
    setStatusMessage(chat.sessionId ? "Loading conversation..." : undefined);
    setProcessUpdates([]);

    if (!chat.sessionId) {
      setMessages([]);
      setPendingProcess(null);
      return;
    }

    try {
      const detail = await getChatSession(chat.sessionId, token, 80);
      setMessages(messagesFromSession(detail.messages));
      setPendingProcess(detail.pending_process?.process_ref ?? null);
      setStatusMessage(`Loaded ${chat.title}`);
      setRecentChats((current) =>
        persistRecentChat(
          {
            conversationId: detail.session.external_conversation_id,
            sessionId: detail.session.session_id,
            title: chat.title,
            lastMessage: detail.messages[detail.messages.length - 1]?.text ?? chat.lastMessage,
            updatedAt: detail.session.updated_at
          },
          current
        )
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load conversation.");
      setStatusMessage(undefined);
    }
  }

  function handleNewChat() {
    if (isSending) {
      return;
    }
    const conversationId = `web-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
    const now = new Date().toISOString();
    setActiveConversationId(conversationId);
    setSessionId(undefined);
    setMessages([]);
    setPendingProcess(null);
    setProcessUpdates([]);
    setStatusMessage("New chat ready");
    setErrorMessage(undefined);
    setRecentChats((current) =>
      persistRecentChat(
        {
          conversationId,
          title: "New chat",
          updatedAt: now
        },
        current
      )
    );
  }

  return (
    <div
      className={`workspace chat-workspace memory-chat-workspace ${
        isHistoryOpen ? "has-chat-history" : "is-chat-history-collapsed"
      }`}
    >
      <aside className="memory-chat-history" aria-label="Recent chats">
        <header className="memory-chat-history-header">
          <strong>Chats</strong>
          <button
            className="memory-icon-button"
            type="button"
            title="Close recent chats"
            aria-label="Close recent chats"
            onClick={() => setIsHistoryOpen(false)}
          >
            <ChatSidebarIcon name="panel" />
          </button>
        </header>
        <button className="memory-chat-history-action" type="button" onClick={handleNewChat}>
          <ChatSidebarIcon name="new" />
          <span>New chat</span>
        </button>
        <div className="memory-chat-history-search">
          <ChatSidebarIcon name="search" />
          <input
            type="search"
            value={recentSearch}
            placeholder="Search chat"
            aria-label="Search recent chats"
            onChange={(event) => setRecentSearch(event.target.value)}
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
              <button
                className={`memory-chat-recent ${
                  chat.conversationId === activeConversationId ? "is-active" : ""
                }`}
                type="button"
                key={chat.conversationId}
                onClick={() => void handleSelectChat(chat)}
              >
                <span>{chat.title}</span>
                {chat.lastMessage ? <small>{chat.lastMessage}</small> : null}
              </button>
            ))
          )}
        </div>
      </aside>

      <section className="memory-chat-panel">
        <header className="memory-chat-topbar">
          <div className="memory-chat-title-row">
            <button
              className="memory-icon-button"
              type="button"
              title="Open recent chats"
              aria-label="Open recent chats"
              aria-expanded={isHistoryOpen}
              onClick={() => setIsHistoryOpen((current) => !current)}
            >
              <ChatSidebarIcon name="panel" />
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

        <ChatStatusBar runtime={runtime} />

        <main className="memory-chat-main">
          <ChatMessageList
            messages={messages}
            pendingProcess={pendingProcess}
            isProcessing={isSending}
            processUpdates={processUpdates}
          />
          <ChatComposer value={draft} isSending={isSending} onChange={setDraft} onSubmit={handleSubmit} />
        </main>
      </section>
    </div>
  );
}

function processUpdatesFromSession(detail: ConversationSessionDetail): string[] {
  const updates = [`Session ${detail.session.status}`];
  const active = detail.pending_process?.process_ref;
  if (active) {
    updates.push(`Pending ${active.kind}: ${active.status}`);
    if (active.question) {
      updates.push(active.question);
    }
  }
  const paused = detail.pending_processes?.filter((item) => item.process_ref.status === "paused") ?? [];
  if (paused.length > 0) {
    updates.push(`${paused.length} paused process${paused.length === 1 ? "" : "es"} available`);
  }
  return updates;
}

function createId(): string {
  if ("randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function loadRecentChats(): RecentChatSummary[] {
  try {
    const raw = localStorage.getItem(recentChatStorageKey);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as RecentChatSummary[];
    return Array.isArray(parsed) ? parsed.slice(0, 24) : [];
  } catch {
    return [];
  }
}

function persistRecentChat(
  next: RecentChatSummary,
  current: RecentChatSummary[]
): RecentChatSummary[] {
  const merged = [
    next,
    ...current.filter((chat) => chat.conversationId !== next.conversationId)
  ].slice(0, 24);
  localStorage.setItem(recentChatStorageKey, JSON.stringify(merged));
  return merged;
}

function chatTitle(messages: RenderedChatMessage[]): string {
  const firstUserMessage = messages.find((message) => message.role === "user")?.text;
  if (!firstUserMessage) {
    return "New chat";
  }
  return firstUserMessage.length > 46 ? `${firstUserMessage.slice(0, 43)}...` : firstUserMessage;
}

function filterRecentChats(chats: RecentChatSummary[], search: string): RecentChatSummary[] {
  const query = search.trim().toLowerCase();
  if (!query) {
    return chats;
  }
  return chats.filter((chat) =>
    `${chat.title} ${chat.lastMessage ?? ""}`.toLowerCase().includes(query)
  );
}

function messagesFromSession(messages: ConversationMessage[]): RenderedChatMessage[] {
  return messages
    .filter((message) => message.role === "user" || message.role === "assistant")
    .map((message) => ({
      id: message.channel_message_id ?? message.message_id,
      role: (message.role === "user" ? "user" : "assistant") as "user" | "assistant",
      text: message.text ?? "",
      createdAt: message.created_at,
      status:
        typeof message.metadata.status === "string" ? message.metadata.status : undefined
    }));
}

function ChatSidebarIcon({ name }: { name: "panel" | "new" | "search" }) {
  if (name === "new") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="M4 20h16M5.5 14.5 15.8 4.2a2 2 0 0 1 2.8 2.8L8.3 17.3 4 18.5l1.5-4Z" />
      </svg>
    );
  }
  if (name === "search") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="m20 20-4.4-4.4M10.5 17a6.5 6.5 0 1 1 0-13 6.5 6.5 0 0 1 0 13Z" />
      </svg>
    );
  }
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5v-13ZM9 4v16" />
    </svg>
  );
}
