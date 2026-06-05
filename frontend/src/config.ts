export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export const defaultWebChatToken = import.meta.env.VITE_WEB_CHAT_AUTH_TOKEN ?? "change-me-web-chat-token";
export const defaultOwnerId = import.meta.env.VITE_OWNER_ID ?? "owner-local";
export const defaultSenderId = import.meta.env.VITE_SENDER_ID ?? defaultOwnerId;
export const defaultConversationId = import.meta.env.VITE_CONVERSATION_ID ?? "web-local";
export const aiTraceDebugEnabled = import.meta.env.VITE_AI_TRACE_DEBUG_ENABLED === "true";
