import type { PendingProcessRef } from "../../types/chat";

export interface RenderedChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
  status?: string;
}

export interface ChatRuntimeState {
  pendingProcess?: PendingProcessRef | null;
  activeClarification?: boolean;
  isSending: boolean;
  statusMessage?: string;
  errorMessage?: string;
}
