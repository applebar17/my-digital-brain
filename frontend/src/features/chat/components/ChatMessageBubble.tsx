import type { RenderedChatMessage } from "../types";

interface ChatMessageBubbleProps {
  message: RenderedChatMessage;
}

export function ChatMessageBubble({ message }: ChatMessageBubbleProps) {
  return (
    <article className={`memory-chat-message memory-chat-message-${message.role}`}>
      <div className="memory-chat-bubble">
        <p>{message.text}</p>
      </div>
      <span className="memory-chat-time">{formatTime(message.createdAt)}</span>
    </article>
  );
}

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}
