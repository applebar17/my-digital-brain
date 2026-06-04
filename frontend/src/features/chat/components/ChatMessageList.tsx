import { useEffect, useRef } from "react";
import { EmptyState } from "../../../components/EmptyState";
import type {
  ClarificationAnswerPacket,
  ClarificationPacket,
  PendingProcessRef
} from "../../../types/chat";
import { ChatMessageBubble } from "./ChatMessageBubble";
import { ClarificationQuestionBox } from "./ClarificationQuestionBox";
import { PendingProcessNotice } from "./PendingProcessNotice";
import type { RenderedChatMessage } from "../types";

interface ChatMessageListProps {
  messages: RenderedChatMessage[];
  pendingProcess?: PendingProcessRef | null;
  clarificationPacket?: ClarificationPacket | null;
  isProcessing?: boolean;
  processUpdates?: string[];
  onSubmitClarification?: (packet: ClarificationAnswerPacket) => void;
}

export function ChatMessageList({
  messages,
  pendingProcess,
  clarificationPacket,
  isProcessing = false,
  processUpdates = [],
  onSubmitClarification
}: ChatMessageListProps) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, pendingProcess, isProcessing, processUpdates.length]);

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
      <ClarificationQuestionBox
        packet={clarificationPacket}
        isSubmitting={isProcessing}
        onSubmit={(packet) => onSubmitClarification?.(packet)}
      />
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
