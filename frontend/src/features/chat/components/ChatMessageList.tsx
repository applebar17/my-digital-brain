import { useEffect, useRef } from "react";
import { EmptyState } from "../../../components/EmptyState";
import type { PendingProcessRef } from "../../../types/chat";
import { ChatMessageBubble } from "./ChatMessageBubble";
import { PendingProcessNotice } from "./PendingProcessNotice";
import type { RenderedChatMessage } from "../types";

interface ChatMessageListProps {
  messages: RenderedChatMessage[];
  pendingProcess?: PendingProcessRef | null;
}

export function ChatMessageList({ messages, pendingProcess }: ChatMessageListProps) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, pendingProcess]);

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
      <PendingProcessNotice pendingProcess={pendingProcess} />
      <div ref={endRef} />
    </section>
  );
}
