import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  createChatSession,
  getChatSession,
  listChatSessions,
  postChatMessage,
  updateChatSession
} from "../api/chat";
import {
  defaultConversationId,
  defaultOwnerId,
  defaultSenderId,
  defaultWebChatToken
} from "../config";
import { ChatComposer } from "../features/chat/components/ChatComposer";
import { ChatHistorySidebar } from "../features/chat/components/ChatHistorySidebar";
import { ChatMessageList } from "../features/chat/components/ChatMessageList";
import { ChatStatusBar } from "../features/chat/components/ChatStatusBar";
import { ChatTopbar } from "../features/chat/components/ChatTopbar";
import type { ChatRuntimeState, RenderedChatMessage } from "../features/chat/types";
import {
  createClientMessageId,
  messagesFromSession,
  processUpdatesFromSession
} from "../features/chat/utils/chatSession";
import type {
  ChatResponse,
  ConversationSessionDetail,
  ConversationSessionSummary,
  PendingProcessRef
} from "../types/chat";

const tokenStorageKey = "my-digital-brain.web-chat-token";

export function ChatView() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<RenderedChatMessage[]>([]);
  const [pendingProcess, setPendingProcess] = useState<PendingProcessRef | null>(null);
  const [sessionId, setSessionId] = useState<string>();
  const [activeConversationId, setActiveConversationId] = useState(defaultConversationId);
  const [isHistoryOpen, setIsHistoryOpen] = useState(true);
  const [recentChats, setRecentChats] = useState<ConversationSessionSummary[]>([]);
  const [recentSearch, setRecentSearch] = useState("");
  const [openChatMenuId, setOpenChatMenuId] = useState<string>();
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

  useEffect(() => {
    let isCancelled = false;

    async function loadInitialSessions() {
      try {
        const list = await listChatSessions(defaultOwnerId, token, { channel: "web", limit: 50 });
        if (isCancelled) {
          return;
        }
        setRecentChats(list.sessions);
        if (!sessionId && list.sessions.length > 0) {
          await loadSession(list.sessions[0], { setLoadedStatus: false });
        }
      } catch (error) {
        if (!isCancelled) {
          setErrorMessage(error instanceof Error ? error.message : "Unable to load chats.");
        }
      }
    }

    void loadInitialSessions();
    return () => {
      isCancelled = true;
    };
    // Initial backend-backed recent chat load only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

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

    const messageId = createClientMessageId();
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
          session_id: sessionId,
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
      await reloadSession(response.session_id, response);
      try {
        await refreshRecentChats();
      } catch {
        setProcessUpdates(["Response received", "Recent chat list will refresh on reload"]);
      }
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

  async function handleSelectChat(chat: ConversationSessionSummary) {
    if (isSending) {
      return;
    }
    setOpenChatMenuId(undefined);
    await loadSession(chat, { setLoadedStatus: true });
  }

  async function loadSession(
    chat: ConversationSessionSummary,
    options: { setLoadedStatus: boolean }
  ) {
    setActiveConversationId(chat.external_conversation_id);
    setSessionId(chat.session_id);
    setErrorMessage(undefined);
    setStatusMessage(options.setLoadedStatus ? "Loading conversation..." : undefined);
    setProcessUpdates([]);
    try {
      const detail = await getChatSession(chat.session_id, token, 80);
      applySessionDetail(detail);
      setStatusMessage(options.setLoadedStatus ? `Loaded ${detail.session.title}` : undefined);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load conversation.");
      setStatusMessage(undefined);
    }
  }

  function handleNewChat() {
    if (isSending) {
      return;
    }
    void createNewChat();
  }

  async function createNewChat() {
    setErrorMessage(undefined);
    setStatusMessage("Creating new chat...");
    setProcessUpdates([]);
    try {
      const session = await createChatSession(
        {
          owner_id: defaultOwnerId,
          channel: "web",
          title: "New chat"
        },
        token
      );
      setActiveConversationId(session.external_conversation_id);
      setSessionId(session.session_id);
      setMessages([]);
      setPendingProcess(null);
      await refreshRecentChats();
      setStatusMessage("New chat ready");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to create chat.");
      setStatusMessage(undefined);
    }
  }

  async function reloadSession(nextSessionId: string, fallbackResponse?: ChatResponse) {
    try {
      const detail = await getChatSession(nextSessionId, token, 80);
      applySessionDetail(detail);
    } catch {
      if (fallbackResponse) {
        setMessages((current) => [
          ...current,
          {
            id: fallbackResponse.response_id,
            role: "assistant",
            text: fallbackResponse.primary_text,
            createdAt: fallbackResponse.created_at,
            status: fallbackResponse.status
          }
        ]);
        return;
      }
      setErrorMessage("The session could not be reloaded.");
    }
  }

  async function refreshRecentChats() {
    const list = await listChatSessions(defaultOwnerId, token, { channel: "web", limit: 50 });
    setRecentChats(list.sessions);
    return list.sessions;
  }

  function applySessionDetail(detail: ConversationSessionDetail) {
    setActiveConversationId(detail.session.external_conversation_id);
    setSessionId(detail.session.session_id);
    setMessages(messagesFromSession(detail.messages));
    setPendingProcess(detail.pending_process?.process_ref ?? null);
  }

  async function handleDeleteChat(chat: ConversationSessionSummary) {
    if (isSending) {
      return;
    }
    setOpenChatMenuId(undefined);
    setErrorMessage(undefined);
    setStatusMessage("Deleting chat...");
    try {
      await updateChatSession(chat.session_id, { status: "archived" }, token);
      const nextChats = await refreshRecentChats();
      if (chat.session_id === sessionId) {
        const nextActive = nextChats.find((item) => item.session_id !== chat.session_id);
        if (nextActive) {
          await loadSession(nextActive, { setLoadedStatus: false });
        } else {
          setSessionId(undefined);
          setActiveConversationId(defaultConversationId);
          setMessages([]);
          setPendingProcess(null);
          setProcessUpdates([]);
        }
      }
      setStatusMessage("Chat deleted");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to delete chat.");
      setStatusMessage(undefined);
    }
  }

  return (
    <div
      className={`workspace chat-workspace memory-chat-workspace ${
        isHistoryOpen ? "has-chat-history" : "is-chat-history-collapsed"
      }`}
    >
      <ChatHistorySidebar
        recentChats={recentChats}
        recentSearch={recentSearch}
        selectedSessionId={sessionId}
        openMenuId={openChatMenuId}
        onSearchChange={setRecentSearch}
        onNewChat={handleNewChat}
        onClose={() => setIsHistoryOpen(false)}
        onSelectChat={(chat) => void handleSelectChat(chat)}
        onToggleMenu={(nextSessionId) =>
          setOpenChatMenuId((current) => (current === nextSessionId ? undefined : nextSessionId))
        }
        onDeleteChat={(chat) => void handleDeleteChat(chat)}
      />

      <section className="memory-chat-panel">
        <ChatTopbar
          activeConversationId={activeConversationId}
          isHistoryOpen={isHistoryOpen}
          onToggleHistory={() => setIsHistoryOpen((current) => !current)}
        />

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
