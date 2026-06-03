import { FormEvent, useMemo, useState } from "react";
import { cancelChatSessionProcess, postChatMessage } from "../api/chat";
import {
  defaultConversationId,
  defaultOwnerId,
  defaultSenderId,
  defaultWebChatToken
} from "../config";
import { Badge } from "../components/Badge";
import { EmptyState } from "../components/EmptyState";
import { Panel } from "../components/Panel";
import { StatusLine } from "../components/StatusLine";
import type { ChatEvidenceRef, ChatResponse, PendingProcessRef } from "../types/chat";

interface RenderedMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
  status?: string;
  pendingProcess?: PendingProcessRef | null;
  evidence?: ChatEvidenceRef[];
}

const tokenStorageKey = "my-digital-brain.web-chat-token";

export function ChatView() {
  const [conversationId, setConversationId] = useState(defaultConversationId);
  const [ownerId, setOwnerId] = useState(defaultOwnerId);
  const [senderId, setSenderId] = useState(defaultSenderId);
  const [token, setToken] = useState(() => {
    return localStorage.getItem(tokenStorageKey) ?? defaultWebChatToken;
  });
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<RenderedMessage[]>([]);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [pendingProcess, setPendingProcess] = useState<PendingProcessRef | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>();
  const [errorMessage, setErrorMessage] = useState<string>();

  const evidence = useMemo(() => lastResponse?.evidence ?? [], [lastResponse]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || isSending) {
      return;
    }

    setDraft("");
    setIsSending(true);
    setErrorMessage(undefined);
    setStatusMessage("Sending message...");

    const messageId = createId();
    const userMessage: RenderedMessage = {
      id: messageId,
      role: "user",
      text,
      createdAt: new Date().toISOString()
    };
    setMessages((current) => [...current, userMessage]);

    try {
      const response = await postChatMessage(
        {
          conversation_id: conversationId,
          sender_id: senderId,
          owner_id: ownerId,
          message_id: messageId,
          text,
          pending_process_id: pendingProcess?.process_id ?? undefined,
          conversation_history_refs: messages.map((message) => message.id)
        },
        token
      );
      localStorage.setItem(tokenStorageKey, token);
      setLastResponse(response);
      setSessionId(response.session_id);
      setPendingProcess(response.pending_process ?? null);
      setMessages((current) => [
        ...current,
        {
          id: response.response_id,
          role: "assistant",
          text: response.primary_text,
          createdAt: response.created_at,
          status: response.status,
          pendingProcess: response.pending_process,
          evidence: response.evidence
        }
      ]);
      setStatusMessage(`Response received: ${response.status}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to send message.");
      setStatusMessage(undefined);
    } finally {
      setIsSending(false);
    }
  }

  async function handleCancelProcess() {
    if (!sessionId) {
      setErrorMessage("No active session is available yet.");
      return;
    }
    setIsSending(true);
    setErrorMessage(undefined);
    setStatusMessage("Cancelling pending process...");
    try {
      const response = await cancelChatSessionProcess(
        sessionId,
        ownerId,
        token,
        "Cancelled from web chat."
      );
      setLastResponse(response);
      setPendingProcess(response.pending_process ?? null);
      setMessages((current) => [
        ...current,
        {
          id: response.response_id,
          role: "assistant",
          text: response.primary_text,
          createdAt: response.created_at,
          status: response.status,
          evidence: response.evidence
        }
      ]);
      setStatusMessage(`Process cancelled: ${response.status}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to cancel process.");
      setStatusMessage(undefined);
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="workspace chat-workspace">
      <div className="workspace-header">
        <div>
          <p className="eyebrow">Conversation Runtime</p>
          <h2>Chat</h2>
        </div>
        <Badge tone={pendingProcess ? "warning" : "trust"}>
          {pendingProcess ? "Pending input" : "Ready"}
        </Badge>
      </div>

      <div className="chat-layout">
        <Panel title="Conversation" eyebrow="Web Chat">
          {pendingProcess && (
            <div className="pending-banner">
              <div>
                <strong>{pendingProcess.kind}</strong>
                <p>{pendingProcess.question ?? "The backend is waiting for follow-up context."}</p>
              </div>
              <button className="button-secondary" type="button" onClick={handleCancelProcess}>
                Cancel
              </button>
            </div>
          )}

          <div className="message-list" aria-live="polite">
            {messages.length === 0 ? (
              <EmptyState
                title="No messages yet"
                body="Send a memory, ask a question, or answer a pending clarification."
              />
            ) : (
              messages.map((message) => <MessageBubble key={message.id} message={message} />)
            )}
          </div>

          <form className="composer" onSubmit={handleSubmit}>
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Write a memory or ask about the graph..."
              rows={3}
            />
            <div className="composer-actions">
              <StatusLine status={errorMessage ? "error" : "success"} message={errorMessage ?? statusMessage} />
              <button className="button-primary" type="submit" disabled={isSending || !draft.trim()}>
                {isSending ? "Sending" : "Send"}
              </button>
            </div>
          </form>
        </Panel>

        <aside className="side-stack">
          <Panel title="Connection" eyebrow="Local API">
            <div className="field-stack">
              <label>
                Bearer token
                <input
                  value={token}
                  onChange={(event) => setToken(event.target.value)}
                  type="password"
                  autoComplete="off"
                />
              </label>
              <label>
                Conversation id
                <input value={conversationId} onChange={(event) => setConversationId(event.target.value)} />
              </label>
              <label>
                Owner id
                <input value={ownerId} onChange={(event) => setOwnerId(event.target.value)} />
              </label>
              <label>
                Sender id
                <input value={senderId} onChange={(event) => setSenderId(event.target.value)} />
              </label>
            </div>
          </Panel>

          <Panel title="Evidence" eyebrow="Response Sidecars">
            {evidence.length === 0 ? (
              <EmptyState title="No evidence returned" body="Evidence references will appear here after grounded answers." />
            ) : (
              <div className="evidence-list">
                {evidence.map((item) => (
                  <article className="evidence-item" key={item.evidence_id}>
                    <strong>{item.title ?? item.source_id ?? item.node_id ?? item.evidence_id}</strong>
                    {item.summary && <p>{item.summary}</p>}
                    <div className="badge-row">
                      {item.source_id && <Badge>Source</Badge>}
                      {item.node_id && <Badge tone="info">Node</Badge>}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </Panel>
        </aside>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: RenderedMessage }) {
  return (
    <article className={`message message-${message.role}`}>
      <div className="message-meta">
        <span>{message.role}</span>
        {message.status && <Badge tone={message.status === "failed" ? "danger" : "neutral"}>{message.status}</Badge>}
      </div>
      <p>{message.text}</p>
      {message.evidence && message.evidence.length > 0 && (
        <div className="badge-row">
          <Badge tone="info">{message.evidence.length} evidence refs</Badge>
        </div>
      )}
    </article>
  );
}

function createId(): string {
  if ("randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
