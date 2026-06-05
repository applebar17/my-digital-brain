/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_WEB_CHAT_AUTH_TOKEN?: string;
  readonly VITE_OWNER_ID?: string;
  readonly VITE_SENDER_ID?: string;
  readonly VITE_CONVERSATION_ID?: string;
  readonly VITE_AI_TRACE_DEBUG_ENABLED?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
