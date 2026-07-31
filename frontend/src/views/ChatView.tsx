import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  createChatSession,
  getChatSession,
  listChatSessions,
  postChatMessage,
  submitClarificationAnswers,
  updateChatSession
} from "../api/chat";
import { clarificationApiError, formatApiError } from "../api/http";
import {
  defaultConversationId,
  aiTraceDebugEnabled,
  defaultOwnerId,
  defaultSenderId,
  defaultWebChatToken
} from "../config";
import { ChatComposer } from "../features/chat/components/ChatComposer";
import { ChatHistorySidebar } from "../features/chat/components/ChatHistorySidebar";
import { ChatMessageList } from "../features/chat/components/ChatMessageList";
import { ClarificationQuestionBox } from "../features/chat/components/ClarificationQuestionBox";
import { ChatStatusBar } from "../features/chat/components/ChatStatusBar";
import { ChatTopbar } from "../features/chat/components/ChatTopbar";
import type {
  ChatRuntimeState,
  ClarificationUiError,
  RenderedChatMessage
} from "../features/chat/types";
import {
  createClientMessageId,
  messagesFromSession,
  processUpdatesFromSession
} from "../features/chat/utils/chatSession";
import type {
  ChatResponse,
  ClarificationAnswerPacket,
  ClarificationPacket,
  ClarificationProgress,
  ConversationSessionDetail,
  ConversationSessionSummary
} from "../types/chat";

const tokenStorageKey = "my-digital-brain.web-chat-token";

export function ChatView() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<RenderedChatMessage[]>([]);
  const [clarificationPacket, setClarificationPacket] = useState<ClarificationPacket | null>(null);
  const [clarificationProgress, setClarificationProgress] = useState<ClarificationProgress | null>(
    null
  );
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
  const [clarificationError, setClarificationError] = useState<ClarificationUiError>();
  const [token] = useState(() => localStorage.getItem(tokenStorageKey) ?? defaultWebChatToken);

  const runtime: ChatRuntimeState = {
    status: clarificationError || errorMessage
      ? "error"
      : clarificationPacket
        ? "awaiting_clarification"
        : isSending
          ? "processing"
          : statusMessage?.startsWith("Response received")
            ? "completed"
            : "active",
    isSending,
    statusMessage,
    errorMessage,
    clarificationError
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
        setClarificationPacket(clarificationPacketFromSession(detail));
        setClarificationProgress(clarificationProgressFromSession(detail));
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
    setClarificationError(undefined);
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
          conversation_history_refs: messages.map((message) => message.id)
        },
        token
      );

      setSessionId(response.session_id);
      setClarificationPacket(response.clarification_packet ?? null);
      setClarificationProgress(clarificationProgressFromResponse(response));
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
      setErrorMessage(formatApiError(error, "Unable to send message."));
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
    setClarificationError(undefined);
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
      setClarificationPacket(null);
      setClarificationProgress(null);
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
          ...(fallbackResponse.clarification_packet
            ? []
            : [
                {
                  id: fallbackResponse.response_id,
                  role: "assistant" as const,
                  text: fallbackResponse.primary_text,
                  createdAt: fallbackResponse.created_at,
                  status: fallbackResponse.status
                }
              ])
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
    setClarificationPacket(clarificationPacketFromSession(detail));
    setClarificationProgress(clarificationProgressFromSession(detail));
  }

  async function handleSubmitClarification(answerPacket: ClarificationAnswerPacket) {
    if (!sessionId || isSending) {
      return;
    }
    const messageId = createClientMessageId();
    setIsSending(true);
    setErrorMessage(undefined);
    setClarificationError(undefined);
    setStatusMessage("Submitting clarification...");
    setProcessUpdates(["Clarification answers submitted", "Resuming backend process..."]);
    try {
      const response = await submitClarificationAnswers(
        sessionId,
        answerPacket.frame_id,
        {
          owner_id: defaultOwnerId,
          sender_id: defaultSenderId,
          message_id: messageId,
          answer_packet: answerPacket
        },
        token
      );
      setClarificationPacket(response.clarification_packet ?? null);
      setClarificationProgress(clarificationProgressFromResponse(response));
      await reloadSession(response.session_id, response);
      await refreshRecentChats();
      setStatusMessage(`Response received: ${response.status}`);
      setProcessUpdates([`Response received: ${response.status}`]);
      window.setTimeout(() => setProcessUpdates([]), 2600);
    } catch (error) {
      const structuredError = clarificationApiError(error);
      if (structuredError) {
        setClarificationError({
          code: structuredError.code,
          message: structuredError.message,
          packetId: structuredError.packetId,
          frameId: structuredError.frameId,
          questionIds: structuredError.questionIds,
          retryable: structuredError.retryable,
          details: structuredError.details
        });
      } else {
        setErrorMessage(formatApiError(error, "Unable to submit clarification."));
      }
      setStatusMessage(undefined);
    } finally {
      setIsSending(false);
    }
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
          setClarificationPacket(null);
          setClarificationProgress(null);
          setProcessUpdates([]);
        }
      }
      setStatusMessage("Chat deleted");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to delete chat.");
      setStatusMessage(undefined);
    }
  }

  function handleOpenTrace() {
    if (sessionId) {
      window.location.hash = `debug/${sessionId}`;
      return;
    }
    window.location.hash = "debug";
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
          traceEnabled={aiTraceDebugEnabled}
          onOpenTrace={handleOpenTrace}
        />

        <ChatStatusBar runtime={runtime} />

        <main className="memory-chat-main">
          <ChatMessageList
            messages={messages}
            isProcessing={isSending}
            processUpdates={processUpdates}
          />
          {clarificationPacket ? (
            <div className="memory-clarification-panel">
              <ClarificationQuestionBox
                packet={clarificationPacket}
                progress={clarificationProgress}
                error={clarificationError}
                isSubmitting={isSending}
                onRecover={
                  sessionId
                    ? () => {
                        setClarificationError(undefined);
                        void reloadSession(sessionId);
                      }
                    : undefined
                }
                onSubmit={(packet) => void handleSubmitClarification(packet)}
              />
            </div>
          ) : null}
          <ChatComposer value={draft} isSending={isSending} onChange={setDraft} onSubmit={handleSubmit} />
        </main>
      </section>
    </div>
  );
}

function clarificationPacketFromSession(
  detail: ConversationSessionDetail
): ClarificationPacket | null {
  const framePacket = detail.active_agentic_frame?.clarification_packet;
  if (isClarificationPacket(framePacket)) {
    return framePacket;
  }
  return null;
}

function clarificationProgressFromSession(
  detail: ConversationSessionDetail
): ClarificationProgress | null {
  const progress = detail.active_agentic_frame?.metadata.clarification_progress;
  return isClarificationProgress(progress) ? progress : null;
}

function clarificationProgressFromResponse(response: ChatResponse): ClarificationProgress | null {
  const progress = response.metadata.clarification_progress;
  return isClarificationProgress(progress) ? progress : null;
}

function isClarificationPacket(value: unknown): value is ClarificationPacket {
  if (!value || typeof value !== "object") {
    return false;
  }
  const packet = value as Partial<ClarificationPacket>;
  return (
    typeof packet.packet_id === "string" &&
    typeof packet.frame_id === "string" &&
    Array.isArray(packet.questions)
  );
}

function isClarificationProgress(value: unknown): value is ClarificationProgress {
  if (!value || typeof value !== "object") {
    return false;
  }
  const progress = value as Partial<ClarificationProgress>;
  return (
    typeof progress.packet_id === "string" &&
    Array.isArray(progress.answered_question_ids) &&
    typeof progress.is_complete === "boolean" &&
    Boolean(progress.answers_by_question_id) &&
    typeof progress.answers_by_question_id === "object"
  );
}
