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
  session_id?: string | null;
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

export interface ClarificationOption {
  option_id: string;
  label: string;
  description?: string | null;
  recommended: boolean;
}

export interface ClarificationQuestion {
  question_id: string;
  question: string;
  options: ClarificationOption[];
  free_text_allowed: boolean;
  required: boolean;
  selection_mode: "single" | "multiple";
}

export interface ClarificationPacket {
  packet_id: string;
  process_id: string;
  origin_state_id: string;
  reason: string;
  questions: ClarificationQuestion[];
  compact_summary?: string | null;
  target_refs: string[];
}

export interface ClarificationAnswer {
  question_id: string;
  selected_option_ids: string[];
  free_text?: string | null;
}

export interface ClarificationAnswerPacket {
  packet_id: string;
  process_id: string;
  answers: ClarificationAnswer[];
}

export interface SubmitClarificationAnswersRequest {
  owner_id: string;
  sender_id?: string | null;
  message_id: string;
  answer_packet: ClarificationAnswerPacket;
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
  clarification_packet?: ClarificationPacket | null;
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
  title: string;
  status: string;
  active_pending_process_id?: string | null;
  last_message_at?: string | null;
  archived_at?: string | null;
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

export interface ConversationSessionSummary {
  session_id: string;
  channel: string;
  external_conversation_id: string;
  owner_id: string;
  title: string;
  status: string;
  active_pending_process_id?: string | null;
  pending_process_status?: string | null;
  last_message_preview?: string | null;
  last_message_at?: string | null;
  archived_at?: string | null;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface ConversationSessionList {
  sessions: ConversationSessionSummary[];
}

export interface CreateChatSessionRequest {
  owner_id: string;
  channel?: string;
  title?: string | null;
  external_conversation_id?: string | null;
}

export interface UpdateChatSessionRequest {
  title?: string | null;
  status?: string | null;
}
