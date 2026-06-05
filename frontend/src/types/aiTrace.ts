export interface AIFlowTraceSection {
  title: string;
  content: string;
  content_type: "text" | "json";
}

export interface AIFlowTraceEvent {
  session_id: string;
  message_id?: string | null;
  sequence: number;
  timestamp: string;
  title: string;
  call_kind: string;
  state_id?: string | null;
  purpose?: string | null;
  model?: string | null;
  provider?: string | null;
  prompt_id?: string | null;
  schema_id?: string | null;
  toolbox_name?: string | null;
  status: string;
  sections: AIFlowTraceSection[];
  metadata: Record<string, unknown>;
}

export interface AIFlowTraceEventList {
  session_id: string;
  events: AIFlowTraceEvent[];
  latest_sequence: number;
}
