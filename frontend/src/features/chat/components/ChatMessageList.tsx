import { useEffect, useRef } from "react";
import { EmptyState } from "../../../components/EmptyState";
import type { ChatProcessSnapshot } from "../../../types/chat";
import { ChatMessageBubble } from "./ChatMessageBubble";
import type { RenderedChatMessage } from "../types";

interface ChatMessageListProps {
  messages: RenderedChatMessage[];
  isProcessing?: boolean;
  processSnapshot?: ChatProcessSnapshot;
}

export function ChatMessageList({
  messages,
  isProcessing = false,
  processSnapshot
}: ChatMessageListProps) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, isProcessing, processSnapshot?.current_activity?.sequence]);

  return (
    <section className="memory-chat-thread" aria-live="polite">
      <div className="memory-chat-date-pill">Today</div>
      {messages.length === 0 ? (
        <div className="memory-chat-empty">
          <EmptyState
            title="No messages yet"
            body="Ask a question, record a thought, or answer a pending clarification."
          />
        </div>
      ) : (
        messages.map((message) => <ChatMessageBubble key={message.id} message={message} />)
      )}
      <ProcessingWidget isProcessing={isProcessing} snapshot={processSnapshot} />
      <div ref={endRef} />
    </section>
  );
}

function ProcessingWidget({
  isProcessing,
  snapshot
}: {
  isProcessing: boolean;
  snapshot?: ChatProcessSnapshot;
}) {
  const isWaiting = snapshot?.status === "waiting_for_user";
  const isVisible = isProcessing || snapshot?.status === "working" || isWaiting;
  if (!isVisible) {
    return null;
  }
  const current = snapshot?.current_activity;
  const recent = snapshot?.recent_activities ?? [];
  const summary = isWaiting
    ? "Answer the question below to continue."
    : current?.summary ?? "Working through the request and preparing the next step.";

  return (
    <aside className={`memory-processing-widget ${isWaiting ? "is-waiting" : ""}`} aria-live="polite">
      <span className="memory-processing-pulse" aria-hidden="true" />
      <div>
        <strong>{isWaiting ? "Waiting for your answer" : current?.title ?? "Working on your request"}</strong>
        <p>{summary}</p>
        {recent.length > 0 ? (
          <div className="memory-processing-history" aria-label="Recent progress">
            {recent.slice(-2).map((activity) => (
              <span key={activity.sequence}>{activity.title}</span>
            ))}
          </div>
        ) : null}
      </div>
    </aside>
  );
}
