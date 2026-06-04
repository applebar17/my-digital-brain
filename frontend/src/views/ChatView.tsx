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
import type { ConversationSessionDetail, PendingProcessRef } from "../types/chat";

const tokenStorageKey = "my-digital-brain.web-chat-token";

export function ChatView() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<RenderedChatMessage[]>([]);
  const [pendingProcess, setPendingProcess] = useState<PendingProcessRef | null>(null);
  const [sessionId, setSessionId] = useState<string>();
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
          conversation_id: defaultConversationId,
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

  return (
    <div className="workspace chat-workspace memory-chat-workspace">
      <header className="memory-chat-topbar">
        <div>
          <p className="eyebrow">Conversation Runtime</p>
          <h2>Chat</h2>
        </div>
        <div className="memory-chat-meta">
          <span>Web</span>
          <span>{defaultConversationId}</span>
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
