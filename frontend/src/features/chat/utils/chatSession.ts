import type {
  ConversationMessage,
  ConversationSessionDetail,
  ConversationSessionSummary
} from "../../../types/chat";
import type { RenderedChatMessage } from "../types";

export function processUpdatesFromSession(detail: ConversationSessionDetail): string[] {
  const updates = [`Session ${detail.session.status}`];
  const active = detail.pending_process?.process_ref;
  if (active) {
    updates.push(`Pending ${active.kind}: ${active.status}`);
    if (active.question) {
      updates.push(active.question);
    }
  }
  const paused =
    detail.pending_processes?.filter((item) => item.process_ref.status === "paused") ?? [];
  if (paused.length > 0) {
    updates.push(`${paused.length} paused process${paused.length === 1 ? "" : "es"} available`);
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
    .filter((message) => message.role === "user" || message.role === "assistant")
    .map((message) => ({
      id: message.channel_message_id ?? message.message_id,
      role: (message.role === "user" ? "user" : "assistant") as "user" | "assistant",
      text: message.text ?? "",
      createdAt: message.created_at,
      status: typeof message.metadata.status === "string" ? message.metadata.status : undefined
    }));
}
