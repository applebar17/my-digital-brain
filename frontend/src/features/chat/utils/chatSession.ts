import type {
  ConversationMessage,
  ConversationSessionDetail,
  ConversationSessionSummary
} from "../../../types/chat";
import type { RenderedChatMessage } from "../types";

export function processUpdatesFromSession(detail: ConversationSessionDetail): string[] {
  const updates = [`Session ${detail.session.status}`];
  const frame = detail.active_agentic_frame;
  if (frame) {
    updates.push(`Agentic frame ${frame.status}`);
    if (frame.clarification_packet) {
      updates.push(`${frame.clarification_packet.questions.length} clarification question(s)`);
    }
  }
  return updates;
}

export function createClientMessageId(): string {
  if ("randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function filterRecentChats(
  chats: ConversationSessionSummary[],
  search: string
): ConversationSessionSummary[] {
  const query = search.trim().toLowerCase();
  if (!query) {
    return chats;
  }
  return chats.filter((chat) =>
    `${chat.title} ${chat.last_message_preview ?? ""}`.toLowerCase().includes(query)
  );
}

export function messagesFromSession(messages: ConversationMessage[]): RenderedChatMessage[] {
  return messages
    .filter(
      (message) =>
        (message.role === "user" || message.role === "assistant") &&
        !isUiHiddenMessage(message.metadata)
    )
    .map((message) => ({
      id: message.channel_message_id ?? message.message_id,
      role: (message.role === "user" ? "user" : "assistant") as "user" | "assistant",
      text: message.text ?? "",
      createdAt: message.created_at,
      status: typeof message.metadata.status === "string" ? message.metadata.status : undefined
    }));
}

function isUiHiddenMessage(metadata: Record<string, unknown>): boolean {
  if (metadata.ui_hidden === true) {
    return true;
  }
  return (
    metadata.message_kind === "clarification_prompt" ||
    metadata.message_kind === "clarification_answer"
  );
}
