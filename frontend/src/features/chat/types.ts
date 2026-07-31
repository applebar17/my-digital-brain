export interface RenderedChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
  status?: string;
}

export interface ChatRuntimeState {
  status: ChatRuntimeStatus;
  isSending: boolean;
  statusMessage?: string;
  clarificationError?: ClarificationUiError;
  errorMessage?: string;
}

export type ChatRuntimeStatus =
  | "active"
  | "processing"
  | "awaiting_clarification"
  | "completed"
  | "error";

export interface ClarificationUiError {
  code: string;
  message: string;
  packetId?: string;
  frameId?: string;
  questionIds: string[];
  retryable: boolean;
  details: Record<string, unknown>;
}
