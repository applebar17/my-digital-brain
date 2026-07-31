import { useEffect, useRef } from "react";
import { EmptyState } from "../../../components/EmptyState";
import { ChatMessageBubble } from "./ChatMessageBubble";
import type { RenderedChatMessage } from "../types";

interface ChatMessageListProps {
  messages: RenderedChatMessage[];
  isProcessing?: boolean;
  processUpdates?: string[];
}

export function ChatMessageList({
  messages,
  isProcessing = false,
  processUpdates = []
}: ChatMessageListProps) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, isProcessing, processUpdates.length]);

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
      <ProcessingWidget isVisible={isProcessing || processUpdates.length > 0} updates={processUpdates} />
      <div ref={endRef} />
    </section>
  );
}

function ProcessingWidget({ isVisible, updates }: { isVisible: boolean; updates: string[] }) {
  if (!isVisible) {
    return null;
  }
  const renderedUpdates = updates.length > 0 ? updates.slice(-4) : ["Processing memory context..."];

  return (
    <aside className="memory-processing-widget" aria-live="polite">
      <span className="memory-processing-pulse" aria-hidden="true" />
      <div>
        <strong>Processing</strong>
        {renderedUpdates.map((update) => (
          <p key={update}>{update}</p>
        ))}
      </div>
    </aside>
  );
}
