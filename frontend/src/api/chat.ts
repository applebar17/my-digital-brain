import { apiRequest } from "./http";
import type {
  ChatResponse,
  ConversationSession,
  ConversationSessionDetail,
  ConversationSessionList,
  CreateChatSessionRequest,
  UpdateChatSessionRequest,
  WebChatMessageRequest
} from "../types/chat";

export function createChatSession(
  request: CreateChatSessionRequest,
  bearerToken: string
): Promise<ConversationSession> {
  return apiRequest<ConversationSession>("/chat/sessions", {
    method: "POST",
    body: request,
    bearerToken
  });
}

export function listChatSessions(
  ownerId: string,
  bearerToken: string,
  options: { channel?: string; includeArchived?: boolean; limit?: number } = {}
): Promise<ConversationSessionList> {
  return apiRequest<ConversationSessionList>("/chat/sessions", {
    query: {
      owner_id: ownerId,
      channel: options.channel ?? "web",
      include_archived: options.includeArchived ?? false,
      limit: options.limit ?? 50
    },
    bearerToken
  });
}

export function updateChatSession(
  sessionId: string,
  request: UpdateChatSessionRequest,
  bearerToken: string
): Promise<ConversationSession> {
  return apiRequest<ConversationSession>(`/chat/sessions/${sessionId}`, {
    method: "PATCH",
    body: request,
    bearerToken
  });
}

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
