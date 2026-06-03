import { apiRequest } from "./http";
import type {
  ChatResponse,
  ConversationSessionDetail,
  WebChatMessageRequest
} from "../types/chat";

export function postChatMessage(
  request: WebChatMessageRequest,
  bearerToken: string
): Promise<ChatResponse> {
  return apiRequest<ChatResponse>("/chat/messages", {
    method: "POST",
    body: request,
    bearerToken
  });
}

export function getChatSession(
  sessionId: string,
  bearerToken: string,
  limit = 50
): Promise<ConversationSessionDetail> {
  return apiRequest<ConversationSessionDetail>(`/chat/sessions/${sessionId}`, {
    query: { limit },
    bearerToken
  });
}

export function cancelChatSessionProcess(
  sessionId: string,
  ownerId: string,
  bearerToken: string,
  reason?: string
): Promise<ChatResponse> {
  return apiRequest<ChatResponse>(`/chat/sessions/${sessionId}/cancel`, {
    method: "POST",
    body: { owner_id: ownerId, reason },
    bearerToken
  });
}
