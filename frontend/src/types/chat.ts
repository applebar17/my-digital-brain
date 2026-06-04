export type ChatResponseStatus =
  | "ok"
  | "accepted"
  | "needs_user_input"
  | "failed"
  | "cancelled";

export type ConversationMessageRole = "user" | "assistant" | "system" | "tool";

export interface IncomingMediaRef {
  media_id?: string;
  media_type: string;
  storage_ref?: string | null;
  mime_type?: string | null;
  file_name?: string | null;
  duration_seconds?: number | null;
  metadata?: Record<string, unknown>;
}

export interface WebChatMessageRequest {
  conversation_id: string;
  sender_id: string;
  owner_id: string;
  message_id: string;
  text?: string | null;
  media_refs?: IncomingMediaRef[];
  reply_to_message_id?: string | null;
  pending_process_id?: string | null;
  conversation_history_refs?: string[];
  received_at?: string;
  metadata?: Record<string, unknown>;
}

export interface PendingProcessRef {
  process_id: string;
  kind: string;
  status: string;
  question?: string | null;
  expires_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface ChatAction {
  action_id: string;
  action_type: string;
  label: string;
  parameters: Record<string, unknown>;
  requires_confirmation: boolean;
  metadata: Record<string, unknown>;
}

export interface ChatEvidenceRef {
  evidence_id: string;
  title?: string | null;
  summary?: string | null;
  source_id?: string | null;
  node_id?: string | null;
  metadata: Record<string, unknown>;
}

export interface ChatDiagnostic {
  level: string;
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface ChatResponse {
  response_id: string;
  session_id: string;
  status: ChatResponseStatus;
  primary_text: string;
  pending_process?: PendingProcessRef | null;
  actions: ChatAction[];
  evidence: ChatEvidenceRef[];
  diagnostics: ChatDiagnostic[];
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ConversationSession {
  session_id: string;
  channel: string;
  external_conversation_id: string;
  owner_id: string;
  status: string;
  active_pending_process_id?: string | null;
  last_message_at?: string | null;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface ConversationMessage {
  message_id: string;
  session_id: string;
  channel_message_id?: string | null;
  role: ConversationMessageRole;
  text?: string | null;
  media_refs: IncomingMediaRef[];
  source_ref?: string | null;
  pending_process_id?: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface PendingProcessContext {
  process_ref: PendingProcessRef;
  context: Record<string, unknown>;
  conversation_history_refs: string[];
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface ConversationSessionDetail {
  session: ConversationSession;
  messages: ConversationMessage[];
  pending_process?: PendingProcessContext | null;
  pending_processes?: PendingProcessContext[];
}
